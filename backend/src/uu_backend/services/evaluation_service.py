"""Simplified evaluation service - single LLM call for all comparisons."""

import json
import logging
import time
from collections import defaultdict
from typing import Any, Optional

from asgiref.sync import sync_to_async

from uu_backend.models.evaluation import (
    EvaluationMetrics,
    EvaluationResult,
    FieldComparison,
    FieldMetrics,
    FlattenedMetrics,
    InstanceComparison,
    InstanceMetrics,
    MatchResult,
    MatchType,
)
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.repositories.factory import get_repository
from uu_backend.services.extraction_service import get_extraction_service
from uu_backend.llm.openai_client import get_openai_client

logger = logging.getLogger(__name__)


class EvaluationService:
    """Simplified evaluation service using single LLM call."""
    
    def __init__(self):
        self.extraction_service = get_extraction_service()
        self.doc_repo = get_document_repository()
        self.openai_client = get_openai_client()
    
    async def evaluate_document(
        self,
        document_id: str,
        run_extraction: bool = True
    ) -> EvaluationResult:
        """Evaluate extraction quality for a document."""
        logger.info(f"[EVAL] Starting evaluation for document {document_id}")
        start_time = time.time()
        
        # 1. Get ground truth annotations
        logger.info("[EVAL] Step 1: Fetching ground truth...")
        ground_truth = await self._get_ground_truth(document_id)
        logger.info(f"[EVAL] Found {len(ground_truth)} ground truth annotations")
        
        # 2. Get or run extraction
        logger.info("[EVAL] Step 2: Running extraction...")
        
        # Debug: Check what schema the document is using
        repository = get_repository()
        classification = await sync_to_async(repository.get_classification)(document_id)
        if classification:
            doc_type = await sync_to_async(repository.get_document_type)(classification.document_type_id)
            if doc_type:
                logger.warning(f"[EVAL DEBUG] Document type: {doc_type.name}")
                logger.warning(f"[EVAL DEBUG] Schema fields: {[f.name for f in (doc_type.schema_fields or [])]}")
        
        extraction_start = time.time()
        if run_extraction:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                # Use .extract_auto() method which auto-routes to correct extraction strategy
                # (vision for tables, standard for text-based documents)
                extraction = await loop.run_in_executor(
                    executor,
                    self.extraction_service.extract_auto,
                    document_id
                )
        else:
            extraction = await self._get_cached_extraction(document_id)
        
        extraction_time_ms = (time.time() - extraction_start) * 1000
        logger.info(f"[EVAL] Extraction completed in {extraction_time_ms:.2f}ms")
        
        # 3. Build comparison schema
        logger.info("[EVAL] Step 3: Building comparison schema...")
        comparison_schema = self._build_comparison_schema(ground_truth, extraction)
        logger.info(f"[EVAL] Built schema with {len(comparison_schema)} fields")
        
        # 4. Evaluate all at once with LLM
        logger.info("[EVAL] Step 4: Evaluating with LLM (single call)...")
        eval_results = await self._evaluate_with_llm(comparison_schema)
        logger.info(f"[EVAL] Got {len(eval_results)} evaluation results")
        
        # 5. Build field comparisons from results
        logger.info("[EVAL] Step 5: Building field comparisons...")
        field_comparisons = self._build_field_comparisons(comparison_schema, eval_results)
        
        # 5b. Build instance comparisons (row-based view)
        logger.info("[EVAL] Step 5b: Building instance comparisons...")
        instance_comparisons = self._build_instance_comparisons(field_comparisons)
        
        # 6. Calculate metrics
        logger.info("[EVAL] Step 6: Calculating metrics...")
        metrics = self._calculate_metrics(field_comparisons, instance_comparisons)
        
        evaluation_time_ms = (time.time() - start_time) * 1000
        logger.info(f"[EVAL] Evaluation completed in {evaluation_time_ms:.2f}ms, accuracy={metrics.flattened.accuracy:.2%}")
        
        return EvaluationResult(
            document_id=document_id,
            metrics=metrics,
            field_comparisons=field_comparisons,
            instance_comparisons=instance_comparisons,
            extraction_time_ms=extraction_time_ms,
            evaluation_time_ms=evaluation_time_ms
        )
    
    async def _get_ground_truth(self, document_id: str) -> list[dict]:
        """Get ground truth annotations."""
        from uu_backend.django_data.models import GroundTruthAnnotationModel
        
        annotations = await sync_to_async(list)(
            GroundTruthAnnotationModel.objects.filter(document_id=document_id)
        )
        
        return [
            {
                "field_name": ann.field_name,
                "value": ann.value,
                "instance_num": ann.annotation_data.get("instance_num") if ann.annotation_data else None
            }
            for ann in annotations
        ]
    
    async def _get_cached_extraction(self, document_id: str):
        """Get cached extraction result."""
        return await sync_to_async(self.extraction_service.extract_auto)(document_id)
    
    def _build_comparison_schema(
        self,
        ground_truth: list[dict],
        extraction: Any
    ) -> dict[str, dict]:
        """
        Build comparison schema grouping GT and predictions by field.
        
        For array fields (tables), intelligently groups GT annotations into rows
        by matching field values, not relying on instance_num.
        
        Handles cross-format comparison: old-style (category/subcategory/line_item) 
        GT labels vs new-style (hierarchy_path) predictions.
        
        Returns:
            {
                "field_name": {
                    "ground_truth": [{"value": x, "instance": 1}, ...],
                    "predicted": [{"value": y, "instance": 1}, ...]
                }
            }
        """
        schema = defaultdict(lambda: {"ground_truth": [], "predicted": []})
        
        # First pass: add predicted values to understand structure
        for extracted_field in extraction.fields:
            self._flatten_to_schema(
                extracted_field.field_name,
                extracted_field.value,
                schema
            )
        
        # Check if either predictions OR ground truth use hierarchy_path
        pred_uses_hierarchy_path = any(
            "hierarchy_path" in field_name 
            for field_name in schema.keys()
        )
        gt_uses_hierarchy_path = any(
            "hierarchy_path" in gt["field_name"]
            for gt in ground_truth
        )
        
        # Second pass: transform and normalize if there's a format mismatch
        if pred_uses_hierarchy_path and not gt_uses_hierarchy_path:
            # Predictions use new format, GT uses old format
            # Transform old-style GT to hierarchy_path format
            gt_transformed = self._transform_gt_for_hierarchy_path(ground_truth, schema)
            gt_with_instances = self._assign_gt_instances(gt_transformed, schema)
        elif gt_uses_hierarchy_path and not pred_uses_hierarchy_path:
            # GT uses new format, predictions use old format
            # Synthesize hierarchy_path entries from normalized predictions
            self._synthesize_prediction_hierarchy_paths(schema)
            gt_with_instances = self._assign_gt_instances(ground_truth, schema)
        else:
            # Both use same format (or both have hierarchy_path)
            gt_with_instances = self._assign_gt_instances(ground_truth, schema)
        
        # Add ground truth values with assigned instances
        for gt in gt_with_instances:
            field_name = gt["field_name"]
            schema[field_name]["ground_truth"].append({
                "value": gt["value"],
                "instance": gt.get("instance_num")
            })
        
        return dict(schema)
    
    def _detect_hierarchy_fields(self, gt_list: list[dict], parent: str) -> list[str]:
        """
        Dynamically detect which fields are hierarchy fields based on their values.
        
        Uses content analysis, NOT hardcoded field name patterns.
        """
        # Collect field names with sample values
        field_samples: dict[str, list[any]] = defaultdict(list)
        for gt in gt_list:
            field_key = gt["field_name"].replace(f"{parent}.", "")
            if field_key != "hierarchy_path" and not "_header" in field_key:
                field_samples[field_key].append(gt["value"])
        
        # Analyze each field to determine if it's hierarchy or data
        detected = []
        for field_name, values in field_samples.items():
            # Analyze the values to determine field type
            is_hierarchy = True
            
            for value in values:
                if value is None or str(value).strip() == "":
                    continue
                
                # Use value-based detection
                if not self._is_hierarchy_field(field_name, value):
                    is_hierarchy = False
                    break
            
            if is_hierarchy:
                detected.append(field_name)
        
        return detected
    
    def _transform_gt_for_hierarchy_path(
        self,
        ground_truth: list[dict],
        schema: dict
    ) -> list[dict]:
        """
        Transform old-style GT (category/subcategory/line_item) to new-style (hierarchy_path).
        
        Dynamically detects hierarchy fields instead of using hardcoded list.
        Groups related GT annotations and converts them to hierarchy_path format
        for proper comparison against new extraction format.
        """
        # Group GT by parent field
        gt_by_parent: dict[str, list[dict]] = defaultdict(list)
        for gt in ground_truth:
            parts = gt["field_name"].split(".")
            if len(parts) > 1:
                parent = parts[0]
                gt_by_parent[parent].append(gt)
            else:
                gt_by_parent[gt["field_name"]].append(gt)
        
        transformed = []
        
        for parent, gt_list in gt_by_parent.items():
            # Check if this parent has hierarchy_path in predictions
            has_hierarchy_path = f"{parent}.hierarchy_path" in schema
            
            if not has_hierarchy_path:
                # No hierarchy_path in predictions, keep GT as-is
                transformed.extend(gt_list)
                continue
            
            # Dynamically detect hierarchy fields from GT
            hierarchy_fields = self._detect_hierarchy_fields(gt_list, parent)
            
            if not hierarchy_fields:
                # No hierarchy fields detected, keep as-is
                transformed.extend(gt_list)
                continue
            
            # Group GT by rows
            gt_groups = self._group_gt_by_similarity(gt_list, parent)
            
            # Convert each group to hierarchy_path format
            for group in gt_groups:
                # Extract hierarchy values from this group in consistent order
                hierarchy_parts = []
                other_fields = []
                
                for gt in group:
                    field_key = gt["field_name"].replace(f"{parent}.", "")
                    
                    if field_key in hierarchy_fields:
                        value = gt["value"]
                        if value and str(value).strip():
                            hierarchy_parts.append(str(value).strip())
                    else:
                        # Keep non-hierarchy fields as-is
                        other_fields.append(gt)
                
                # Add a synthetic hierarchy_path GT entry
                if hierarchy_parts:
                    transformed.append({
                        "field_name": f"{parent}.hierarchy_path",
                        "value": hierarchy_parts,
                        "instance_num": group[0].get("instance_num")
                    })
                
                # Add other fields
                transformed.extend(other_fields)
        
        return transformed
    
    def _assign_gt_instances(
        self,
        ground_truth: list[dict],
        schema: dict
    ) -> list[dict]:
        """
        Intelligently assign instance numbers to GT annotations for array fields.
        
        Groups GT annotations into rows by matching their values against extracted
        array items, without relying on pre-assigned instance_num.
        """
        # Group GT by parent field (e.g., "forward_looking_reconciliations")
        gt_by_parent: dict[str, list[dict]] = defaultdict(list)
        for gt in ground_truth:
            parts = gt["field_name"].split(".")
            if len(parts) > 1:
                parent = parts[0]
                gt_by_parent[parent].append(gt)
            else:
                # Not an array field, keep as-is
                gt_by_parent[gt["field_name"]].append(gt)
        
        result = []
        
        for parent, gt_list in gt_by_parent.items():
            # Check if this parent has array structure in predictions
            child_fields = [f for f in schema.keys() if f.startswith(f"{parent}.")]
            
            if not child_fields:
                # Not an array field, add GT as-is
                result.extend(gt_list)
                continue
            
            # Build predicted rows from schema
            predicted_rows = self._extract_predicted_rows(parent, schema)
            
            if not predicted_rows:
                # No predictions, add GT with no instance assignment
                result.extend(gt_list)
                continue
            
            # Match GT annotations to predicted rows
            matched_gt = self._match_gt_to_predicted_rows(gt_list, predicted_rows)
            result.extend(matched_gt)
        
        return result
    
    def _extract_predicted_rows(self, parent: str, schema: dict) -> list[dict]:
        """Extract predicted array rows for a parent field."""
        # Collect all child field predictions
        rows_dict: dict[int, dict] = defaultdict(dict)
        
        for field_name, data in schema.items():
            if not field_name.startswith(f"{parent}."):
                continue
            
            child_key = field_name[len(parent) + 1:]  # Remove "parent." prefix
            
            for pred in data["predicted"]:
                instance = pred["instance"]
                if instance:
                    rows_dict[instance][child_key] = pred["value"]
        
        # Convert to list of rows and normalize hierarchy representation
        rows = []
        for inst, fields in sorted(rows_dict.items()):
            normalized_fields = self._normalize_hierarchy_fields(fields)
            rows.append({"instance": inst, "fields": normalized_fields})
        
        return rows
    
    def _normalize_hierarchy_fields(self, fields: dict) -> dict:
        """
        Normalize hierarchical field representations to a common format.
        
        Converts both old-style (category/subcategory/line_item/level_N) and new-style 
        (hierarchy_path array) to a comparable format.
        
        IMPORTANT: Only includes non-empty hierarchy values to create the path.
        This distinguishes parent rows (e.g., ["GAAP R&D"]) from child rows 
        (e.g., ["GAAP R&D", "Acquisition-related adjustments"]).
        """
        # Check if this row uses hierarchy_path array
        if "hierarchy_path" in fields and isinstance(fields.get("hierarchy_path"), list):
            # Already normalized, return as-is
            return fields
        
        # Check if this row uses old-style hierarchy fields (dynamically detected)
        # Build hierarchy path from non-empty values only
        hierarchy_values = []
        for field_name, value in sorted(fields.items()):
            # Only add if it's a hierarchy field AND has a non-empty value
            if self._is_hierarchy_field(field_name, value):
                value_str = str(value).strip() if value else ""
                if value_str:  # Only add non-empty values
                    hierarchy_values.append(value_str)
        
        # Add normalized hierarchy_path (even if empty, for consistency)
        normalized = fields.copy()
        normalized["_normalized_hierarchy_path"] = hierarchy_values if hierarchy_values else []
        return normalized
    
    def _match_gt_to_predicted_rows(
        self,
        gt_list: list[dict],
        predicted_rows: list[dict]
    ) -> list[dict]:
        """Match GT annotations to predicted rows based on field values."""
        # Extract field names (remove parent prefix)
        parent = gt_list[0]["field_name"].split(".")[0] if gt_list else ""
        
        # Group GT by unique combinations of key fields
        # For tables, we'll try to match based on multiple fields together
        gt_groups = self._group_gt_by_similarity(gt_list, parent)
        
        # Match each GT group to a predicted row
        matched = []
        used_instances = set()
        
        for gt_group in gt_groups:
            best_match_instance = None
            best_match_score = 0
            
            # Find best matching predicted row
            for pred_row in predicted_rows:
                if pred_row["instance"] in used_instances:
                    continue
                
                score = self._calculate_row_match_score(gt_group, pred_row, parent)
                if score > best_match_score:
                    best_match_score = score
                    best_match_instance = pred_row["instance"]
            
            # Assign instance to this group
            for gt in gt_group:
                gt_copy = gt.copy()
                if best_match_instance is not None and best_match_score > 0:
                    gt_copy["instance_num"] = best_match_instance
                    used_instances.add(best_match_instance)
                matched.append(gt_copy)
        
        return matched
    
    def _group_gt_by_similarity(self, gt_list: list[dict], parent: str) -> list[list[dict]]:
        """
        Group GT annotations that likely belong to the same table row.
        
        Uses heuristics like proximity of annotation IDs and field value patterns.
        """
        if not gt_list:
            return []
        
        # Sort by original order (assuming annotations are created in order)
        sorted_gt = sorted(gt_list, key=lambda x: x.get("field_name", ""))
        
        # Group consecutive annotations with similar patterns
        groups = []
        current_group = [sorted_gt[0]]
        
        for i in range(1, len(sorted_gt)):
            curr = sorted_gt[i]
            prev = sorted_gt[i - 1]
            
            # Check if this GT likely belongs with the previous group
            # Heuristic: same parent, and appears soon after
            if self._should_group_together(curr, prev, current_group, parent):
                current_group.append(curr)
            else:
                groups.append(current_group)
                current_group = [curr]
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _should_group_together(
        self,
        curr: dict,
        prev: dict,
        current_group: list[dict],
        parent: str
    ) -> bool:
        """Determine if GT annotation should be grouped with current group."""
        curr_field = curr["field_name"].replace(f"{parent}.", "")
        group_fields = {gt["field_name"].replace(f"{parent}.", "") for gt in current_group}
        
        # If this field is already in the group, it's likely a new row
        if curr_field in group_fields:
            return False
        
        # If current group has a "complete set" of fields, start new row
        # For tables: if we have value fields, and see another hierarchy field, it's a new row
        has_values = any("value" in f for f in group_fields)
        is_hierarchy_field = self._is_hierarchy_field(curr_field, curr.get("value"))
        
        if has_values and is_hierarchy_field:
            return False
        
        return True
    
    def _is_hierarchy_field(self, field_name: str, field_value: any = None) -> bool:
        """
        Check if a field represents hierarchy (structural/categorical) vs data (measurements).
        
        Uses schema structure and value patterns, NOT hardcoded field names.
        """
        # Explicit hierarchy_path field
        if field_name == "hierarchy_path":
            return True
        
        # Headers are not hierarchy
        if "_header" in field_name:
            return False
        
        # If we have the value, use it to detect data fields
        if field_value is not None:
            value_str = str(field_value)
            
            # Data field indicators: contains numbers, currency, dates, ranges
            is_numeric = any(char.isdigit() for char in value_str)
            has_currency = any(symbol in value_str for symbol in ['$', '€', '£', '¥'])
            has_range = '-' in value_str and is_numeric
            is_parenthetical = value_str.strip().startswith('(') and value_str.strip().endswith(')')
            
            # If it looks like a data value, it's NOT hierarchy
            if has_currency or has_range or (is_numeric and is_parenthetical):
                return False
        
        # Default: if it's not clearly a data field, treat as potential hierarchy
        # This is conservative - we'd rather include too many than miss hierarchy fields
        return True
    
    def _calculate_row_match_score(
        self,
        gt_group: list[dict],
        pred_row: dict,
        parent: str
    ) -> float:
        """Calculate how well a GT group matches a predicted row."""
        score = 0.0
        total_fields = 0
        
        # Build GT hierarchy path and field map
        # Track whether GT originally had hierarchy_path as a string (leaf-only label)
        gt_hierarchy = []
        gt_hierarchy_was_string = False
        gt_fields_map = {}
        
        for gt in gt_group:
            field_key = gt["field_name"].replace(f"{parent}.", "")
            value = gt["value"]
            gt_fields_map[field_key] = value
            
            # Collect hierarchy from old-style fields or hierarchy_path
            if field_key == "hierarchy_path":
                if isinstance(value, list):
                    gt_hierarchy = value
                elif value:
                    # GT has hierarchy_path as string (user labeled it as single string)
                    gt_hierarchy_was_string = True
                    gt_hierarchy = [str(value)]
            elif self._is_hierarchy_field(field_key, value) and value and str(value).strip():
                gt_hierarchy.append(str(value).strip())
        
        # Get predicted hierarchy
        pred_hierarchy = []
        pred_hierarchy_was_string = False
        if "hierarchy_path" in pred_row["fields"]:
            pred_value = pred_row["fields"]["hierarchy_path"]
            if isinstance(pred_value, list):
                pred_hierarchy = pred_value
            elif pred_value:
                pred_hierarchy_was_string = True
                pred_hierarchy = [str(pred_value)]
        elif "_normalized_hierarchy_path" in pred_row["fields"]:
            pred_hierarchy = pred_row["fields"]["_normalized_hierarchy_path"] or []
        else:
            # Build from old-style fields
            for field_name, value in pred_row["fields"].items():
                if self._is_hierarchy_field(field_name, value) and value and str(value).strip():
                    pred_hierarchy.append(str(value).strip())
        
        # Compare hierarchy paths
        if gt_hierarchy or pred_hierarchy:
            gt_path_lower = [str(x).strip().lower() for x in gt_hierarchy]
            pred_path_lower = [str(x).strip().lower() for x in pred_hierarchy]
            
            # Check if paths match exactly
            if gt_path_lower == pred_path_lower:
                score += 2.0  # Exact hierarchy match
                total_fields += 1
            # GT is single-element (leaf-only label), pred is full path - check leaf match
            elif gt_hierarchy_was_string and len(gt_path_lower) == 1 and len(pred_path_lower) >= 1:
                gt_leaf = gt_path_lower[0]
                pred_leaf = pred_path_lower[-1]
                if gt_leaf == pred_leaf:
                    score += 2.0  # Leaf node match
                    total_fields += 1
                elif len(pred_path_lower) == 1 and gt_leaf == pred_path_lower[0]:
                    # Single element exact match
                    score += 2.0
                    total_fields += 1
                else:
                    total_fields += 1
            # Pred is single-element (leaf-only), GT is full path - check leaf match
            elif pred_hierarchy_was_string and len(pred_path_lower) == 1 and len(gt_path_lower) >= 1:
                pred_leaf = pred_path_lower[0]
                gt_leaf = gt_path_lower[-1]
                if pred_leaf == gt_leaf:
                    score += 2.0  # Leaf node match
                    total_fields += 1
                else:
                    total_fields += 1
            # Both are arrays - check for subset/partial match
            else:
                gt_path_str = " > ".join(gt_path_lower) if gt_path_lower else ""
                pred_path_str = " > ".join(pred_path_lower) if pred_path_lower else ""
                
                if gt_path_str and pred_path_str:
                    if gt_path_str == pred_path_str:
                        score += 2.0
                    elif gt_path_str in pred_path_str or pred_path_str in gt_path_str:
                        score += 1.0
                    
                    total_fields += 1
        
        # Compare data value fields (not hierarchy, not headers)
        for gt in gt_group:
            field_key = gt["field_name"].replace(f"{parent}.", "")
            value = gt.get("value")
            
            # Skip hierarchy and header fields
            if self._is_hierarchy_field(field_key, value) or field_key == "hierarchy_path" or "_header" in field_key:
                continue
            
            gt_value = str(gt["value"]).strip().lower() if gt["value"] else ""
            
            if field_key in pred_row["fields"]:
                pred_value = str(pred_row["fields"][field_key]).strip().lower() if pred_row["fields"][field_key] else ""
                
                # Exact match
                if gt_value and pred_value and gt_value == pred_value:
                    score += 1.0
                # Partial match (substring)
                elif gt_value and pred_value and (gt_value in pred_value or pred_value in gt_value):
                    score += 0.5
                
                total_fields += 1
        
        return score / total_fields if total_fields > 0 else 0.0
    
    def _flatten_to_schema(
        self,
        prefix: str,
        value: Any,
        schema: dict,
        instance_num: int = None
    ):
        """Flatten extracted values into schema."""
        if value is None or value == "":
            return
        
        # Special case: hierarchy_path arrays should be treated as atomic values
        # The array itself is the value, not a collection to iterate through
        if "hierarchy_path" in prefix and isinstance(value, list):
            # Check if it's a list of strings (the hierarchy path itself)
            if value and all(isinstance(item, str) for item in value):
                schema[prefix]["predicted"].append({
                    "value": value,  # The entire array is the value
                    "instance": instance_num
                })
                return
        
        if isinstance(value, list):
            for idx, item in enumerate(value):
                item_instance = idx + 1
                if isinstance(item, dict):
                    for key, val in item.items():
                        self._flatten_to_schema(f"{prefix}.{key}", val, schema, item_instance)
                else:
                    schema[prefix]["predicted"].append({
                        "value": item,
                        "instance": item_instance
                    })
        elif isinstance(value, dict):
            for key, val in value.items():
                self._flatten_to_schema(f"{prefix}.{key}", val, schema, instance_num)
        else:
            schema[prefix]["predicted"].append({
                "value": value,
                "instance": instance_num
            })
    
    async def _evaluate_with_llm(self, comparison_schema: dict) -> dict:
        """
        Evaluate all fields in a single LLM call.
        
        Returns:
            {
                "field_name": {
                    "matches": [{"gt_idx": 0, "pred_idx": 0, "is_match": true, "confidence": 1.0, "reason": "..."}],
                    "missing": [0, 1],  # GT indices with no match
                    "extra": [2]  # Pred indices with no match
                }
            }
        """
        # Build the prompt
        prompt = self._build_evaluation_prompt(comparison_schema)
        
        try:
            # Single LLM call
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            from functools import partial
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                # Use partial to properly pass keyword arguments
                complete_fn = partial(
                    self.openai_client.complete_json,
                    prompt=prompt,
                    max_completion_tokens=4000
                )
                result = await loop.run_in_executor(executor, complete_fn)
            
            return result.get("evaluations", {})
        except Exception as e:
            logger.error(f"LLM evaluation failed: {e}")
            # Fall back to simple exact matching
            return self._fallback_exact_match(comparison_schema)
    
    def _build_evaluation_prompt(self, comparison_schema: dict) -> str:
        """Build the evaluation prompt for LLM."""
        # Simplify schema for prompt (remove empty fields)
        simplified = {}
        for field_name, data in comparison_schema.items():
            if data["ground_truth"] or data["predicted"]:
                simplified[field_name] = {
                    "ground_truth": [item["value"] for item in data["ground_truth"]],
                    "predicted": [item["value"] for item in data["predicted"]]
                }
        
        prompt = f"""You are evaluating document extraction accuracy. Compare ground truth values against predicted values.

For each field, determine which predictions match which ground truth values.
Consider values as matching if they are semantically equivalent, even with different formatting:
- "$1,000,000" matches "1000000" 
- "01/01/2026" matches "2026-01-01"
- "COMMERCIAL GENERAL LIABILITY" matches "Commercial General Liability"
- Minor OCR errors or whitespace differences should still match

SPECIAL RULES for hierarchy_path fields (these contain hierarchical paths like breadcrumbs):
- String "A" matches array ["A"] ONLY (exact single-level path)
- String "B" matches array ["A", "B"] if "B" is the LAST element (leaf node)
- String "A" does NOT match array ["A", "B"] (different hierarchy depths)
- Array ["A", "B"] matches array ["A", "B"] exactly (full path match)

When GT is a string and prediction is an array for hierarchy_path:
- Match if GT exactly equals the single element: GT="A" matches Pred=["A"]
- OR match if GT equals the LAST element (leaf): GT="B" matches Pred=["A", "B"]
- Example: GT="Partner contributions" matches Pred=["GAAP additions", "Partner contributions"] ✓
- Example: GT="GAAP additions" does NOT match Pred=["GAAP additions", "Partner contributions"] ✗

Here are the fields to evaluate:

{json.dumps(simplified, indent=2)}

Respond with a JSON object in this exact format:
{{
    "evaluations": {{
        "field_name": {{
            "matches": [
                {{"gt_idx": 0, "pred_idx": 0, "is_match": true, "confidence": 0.95, "reason": "Exact match"}},
                {{"gt_idx": 1, "pred_idx": 1, "is_match": true, "confidence": 0.85, "reason": "Same value with different formatting"}}
            ],
            "missing_gt_indices": [],
            "extra_pred_indices": []
        }}
    }}
}}

Rules:
- gt_idx and pred_idx are 0-based indices into the ground_truth and predicted arrays
- Each GT value should match at most one prediction (and vice versa)
- missing_gt_indices: GT values with no matching prediction
- extra_pred_indices: Predictions with no matching GT
- confidence: 0.0-1.0 based on how well they match
- For array fields with multiple instances, match by position/instance when possible"""

        return prompt
    
    def _normalize_value_for_comparison(self, value: any) -> str:
        """Normalize a value for comparison (handles arrays, strings, etc.)."""
        if value is None:
            return ""
        if isinstance(value, list):
            # For arrays (like hierarchy_path), join with separator
            return " > ".join(str(v).strip() for v in value if v)
        return str(value).strip()
    
    def _hierarchy_matches_string(self, hierarchy_array: list, search_value: str) -> bool:
        """
        Check if a hierarchy path array matches a single string GT label.
        
        Matches when:
        1. Array has exactly one element that matches the string (exact match)
        2. The last element (leaf node) of the array matches the string (partial match)
        """
        if not hierarchy_array or not search_value:
            return False
        
        search_lower = search_value.strip().lower()
        
        # Exact match: array is single element matching the string
        if len(hierarchy_array) == 1:
            return str(hierarchy_array[0]).strip().lower() == search_lower
        
        # Leaf match: last element of array matches the string
        return str(hierarchy_array[-1]).strip().lower() == search_lower
    
    def _fallback_exact_match(self, comparison_schema: dict) -> dict:
        """Fallback to simple exact matching if LLM fails."""
        evaluations = {}
        
        for field_name, data in comparison_schema.items():
            gt_values = [item["value"] for item in data["ground_truth"]]
            pred_values = [item["value"] for item in data["predicted"]]
            
            is_hierarchy_path = "hierarchy_path" in field_name
            
            matches = []
            matched_gt = set()
            matched_pred = set()
            
            # Match GT to predictions
            for gt_idx, gt_val in enumerate(gt_values):
                for pred_idx, pred_val in enumerate(pred_values):
                    if pred_idx in matched_pred:
                        continue
                    
                    is_match = False
                    
                    if is_hierarchy_path:
                        # Special handling for hierarchy_path comparisons
                        # Handles multiple formats for backwards compatibility:
                        # 1. GT string (leaf only) vs pred array (full path)
                        # 2. GT comma-separated string vs pred array (old stringified format)
                        # 3. GT array vs pred array (new correct format)
                        is_match = self._compare_hierarchy_values(gt_val, pred_val)
                    else:
                        # Regular field comparison
                        gt_normalized = self._normalize_value_for_comparison(gt_val).lower()
                        pred_normalized = self._normalize_value_for_comparison(pred_val).lower()
                        is_match = gt_normalized == pred_normalized
                    
                    if is_match:
                        matches.append({
                            "gt_idx": gt_idx,
                            "pred_idx": pred_idx,
                            "is_match": True,
                            "confidence": 1.0,
                            "reason": "Match"
                        })
                        matched_gt.add(gt_idx)
                        matched_pred.add(pred_idx)
                        break
            
            evaluations[field_name] = {
                "matches": matches,
                "missing_gt_indices": [i for i in range(len(gt_values)) if i not in matched_gt],
                "extra_pred_indices": [i for i in range(len(pred_values)) if i not in matched_pred]
            }
        
        return evaluations
    
    def _compare_hierarchy_values(self, gt_val: Any, pred_val: Any) -> bool:
        """
        Compare hierarchy_path values with backwards compatibility.
        
        Handles multiple GT formats:
        1. String (leaf only): "Child" matches ["Parent", "Child"]
        2. Comma-separated string: "Parent,Child" matches ["Parent", "Child"]
        3. Array: ["Parent", "Child"] matches ["Parent", "Child"]
        """
        # Normalize both values to arrays for comparison
        gt_array = self._normalize_hierarchy_to_array(gt_val)
        pred_array = self._normalize_hierarchy_to_array(pred_val)
        
        if not gt_array or not pred_array:
            return False
        
        # Normalize for case-insensitive comparison
        gt_lower = [s.strip().lower() for s in gt_array]
        pred_lower = [s.strip().lower() for s in pred_array]
        
        # Exact match (arrays are identical)
        if gt_lower == pred_lower:
            return True
        
        # Leaf match: GT has single element that matches pred's last element
        if len(gt_lower) == 1 and gt_lower[0] == pred_lower[-1]:
            return True
        
        # Leaf match reverse: pred has single element that matches GT's last element
        if len(pred_lower) == 1 and pred_lower[0] == gt_lower[-1]:
            return True
        
        return False
    
    def _normalize_hierarchy_to_array(self, value: Any) -> list[str]:
        """
        Normalize a hierarchy_path value to an array of strings.
        
        Handles:
        - Array: ["A", "B"] -> ["A", "B"]
        - Comma-separated string (no space after comma): "A,B" -> ["A", "B"]
        - Single string: "A" -> ["A"]
        - Text with comma (space after): "Partner contributions, net" -> ["Partner contributions, net"]
        - None/empty: -> []
        
        The key distinction: separator commas have NO space after them (e.g., "A,B"),
        while commas that are part of text have a space (e.g., "A, B").
        """
        import re
        
        if value is None:
            return []
        
        if isinstance(value, list):
            return [str(v) for v in value if v]
        
        if isinstance(value, str):
            if not value.strip():
                return []
            
            # Check if it's a comma-separated string (old stringified array format)
            # Pattern: comma NOT followed by a space indicates a separator
            # "A,B,C" -> split on commas
            # "A, B, C" or "Partner contributions, net" -> treat as single string
            
            # Look for pattern: comma followed by non-space (separator pattern)
            if re.search(r',[^\s]', value):
                # Split only on commas that are NOT followed by space
                parts = re.split(r',(?!\s)', value)
                return [s.strip() for s in parts if s.strip()]
            
            # Single string (may contain commas that are part of text)
            return [value.strip()]
        
        return [str(value)]
    
    def _build_field_comparisons(
        self,
        comparison_schema: dict,
        eval_results: dict
    ) -> list[FieldComparison]:
        """Build FieldComparison objects from evaluation results."""
        comparisons = []
        
        for field_name, data in comparison_schema.items():
            gt_items = data["ground_truth"]
            pred_items = data["predicted"]
            eval_data = eval_results.get(field_name, {})
            
            matches = eval_data.get("matches", [])
            missing_indices = set(eval_data.get("missing_gt_indices", []))
            extra_indices = set(eval_data.get("extra_pred_indices", []))
            
            # Track what's been matched
            matched_gt = set()
            matched_pred = set()
            
            # Process matches
            for match in matches:
                gt_idx = match.get("gt_idx", 0)
                pred_idx = match.get("pred_idx", 0)
                is_match = match.get("is_match", False)
                confidence = match.get("confidence", 0.0)
                reason = match.get("reason", "")
                
                if gt_idx < len(gt_items) and pred_idx < len(pred_items):
                    gt_item = gt_items[gt_idx]
                    pred_item = pred_items[pred_idx]
                    
                    comparisons.append(FieldComparison(
                        field_name=field_name,
                        ground_truth_value=gt_item["value"],
                        predicted_value=pred_item["value"],
                        match_result=MatchResult(
                            is_match=is_match,
                            match_type=MatchType.SEMANTIC if is_match else MatchType.NO_MATCH,
                            confidence=confidence,
                            reason=reason
                        ),
                        instance_num=gt_item.get("instance")
                    ))
                    matched_gt.add(gt_idx)
                    matched_pred.add(pred_idx)
            
            # Add missing (GT with no prediction)
            for gt_idx in missing_indices:
                if gt_idx < len(gt_items) and gt_idx not in matched_gt:
                    gt_item = gt_items[gt_idx]
                    comparisons.append(FieldComparison(
                        field_name=field_name,
                        ground_truth_value=gt_item["value"],
                        predicted_value=None,
                        match_result=MatchResult(
                            is_match=False,
                            match_type=MatchType.NO_MATCH,
                            confidence=0.0,
                            reason="Missing prediction"
                        ),
                        instance_num=gt_item.get("instance")
                    ))
            
            # Add extra (predictions with no GT)
            for pred_idx in extra_indices:
                if pred_idx < len(pred_items) and pred_idx not in matched_pred:
                    pred_item = pred_items[pred_idx]
                    comparisons.append(FieldComparison(
                        field_name=field_name,
                        ground_truth_value=None,
                        predicted_value=pred_item["value"],
                        match_result=MatchResult(
                            is_match=False,
                            match_type=MatchType.NO_MATCH,
                            confidence=0.0,
                            reason="Extra prediction"
                        ),
                        instance_num=pred_item.get("instance")
                    ))
            
            # Handle unprocessed items (if eval_results was incomplete)
            for gt_idx, gt_item in enumerate(gt_items):
                if gt_idx not in matched_gt and gt_idx not in missing_indices:
                    comparisons.append(FieldComparison(
                        field_name=field_name,
                        ground_truth_value=gt_item["value"],
                        predicted_value=None,
                        match_result=MatchResult(
                            is_match=False,
                            match_type=MatchType.NO_MATCH,
                            confidence=0.0,
                            reason="Unprocessed GT"
                        ),
                        instance_num=gt_item.get("instance")
                    ))
        
        return comparisons
    
    def _build_instance_comparisons(
        self,
        field_comparisons: list[FieldComparison]
    ) -> dict[str, list[InstanceComparison]]:
        """Build instance comparisons from field comparisons, grouped by parent and row."""
        from collections import defaultdict
        
        # Group by parent field (e.g., "forward_looking_reconciliations")
        parent_groups: dict[str, dict[int, list[FieldComparison]]] = defaultdict(lambda: defaultdict(list))
        
        for comp in field_comparisons:
            parts = comp.field_name.split(".")
            if len(parts) > 1:
                parent = parts[0]
                child_field = parts[1]
                
                # Skip header fields from instance comparisons
                if "_header" in child_field:
                    continue
                
                instance = comp.instance_num or 1
                parent_groups[parent][instance].append(comp)
        
        # Build InstanceComparison objects
        result = {}
        for parent, instances in parent_groups.items():
            instance_list = []
            for instance_num in sorted(instances.keys()):
                comps = instances[instance_num]
                
                # Calculate match score for this instance
                total_fields = len(comps)
                matched_fields = sum(1 for c in comps if c.is_correct)
                match_score = matched_fields / total_fields if total_fields > 0 else 0.0
                is_matched = match_score > 0.5  # Consider matched if >50% fields correct
                
                instance_list.append(InstanceComparison(
                    parent_field=parent,
                    instance_num=instance_num,
                    gt_instance_num=instance_num,
                    pred_instance_num=instance_num,
                    field_comparisons=comps,
                    is_matched=is_matched,
                    match_score=match_score
                ))
            
            result[parent] = instance_list
        
        return result
    
    def _calculate_metrics(
        self,
        comparisons: list[FieldComparison],
        instance_comparisons: dict[str, list[InstanceComparison]]
    ) -> EvaluationMetrics:
        """Calculate evaluation metrics."""
        # Filter out header fields from flattened metrics
        value_comparisons = [
            c for c in comparisons 
            if "_header" not in c.field_name.split(".")[-1]
        ]
        
        flattened = self._calculate_flattened_metrics(value_comparisons)
        field_metrics = self._calculate_field_metrics(value_comparisons)
        instance_metrics = self._calculate_instance_metrics(instance_comparisons)
        
        return EvaluationMetrics(
            flattened=flattened,
            instance_metrics=instance_metrics,
            field_metrics=field_metrics
        )
    
    def _calculate_flattened_metrics(self, comparisons: list[FieldComparison]) -> FlattenedMetrics:
        """Calculate flattened metrics."""
        total_gt = sum(1 for c in comparisons if c.ground_truth_value is not None)
        total_pred = sum(1 for c in comparisons if c.predicted_value is not None)
        correct = sum(1 for c in comparisons if c.is_correct)
        incorrect = sum(1 for c in comparisons if not c.is_correct and not c.is_missing and not c.is_extra)
        missing = sum(1 for c in comparisons if c.is_missing)
        extra = sum(1 for c in comparisons if c.is_extra)
        
        accuracy = correct / total_gt if total_gt > 0 else 0.0
        precision = correct / total_pred if total_pred > 0 else 0.0
        recall = correct / total_gt if total_gt > 0 else 0.0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
        
        match_type_dist = {}
        for c in comparisons:
            match_type = c.match_result.match_type.value
            match_type_dist[match_type] = match_type_dist.get(match_type, 0) + 1
        
        return FlattenedMetrics(
            total_fields=total_gt,
            correct_fields=correct,
            incorrect_fields=incorrect,
            missing_fields=missing,
            extra_fields=extra,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            match_type_distribution=match_type_dist
        )
    
    def _calculate_instance_metrics(
        self,
        instance_comparisons: dict[str, list[InstanceComparison]]
    ) -> dict[str, InstanceMetrics]:
        """Calculate instance-level metrics (row-based)."""
        metrics = {}
        
        for parent, instances in instance_comparisons.items():
            total_instances = len(instances)
            matched_instances = sum(1 for inst in instances if inst.is_matched)
            
            # Calculate GT vs predicted instance counts
            gt_instances = len([i for i in instances if any(c.ground_truth_value is not None for c in i.field_comparisons)])
            pred_instances = len([i for i in instances if any(c.predicted_value is not None for c in i.field_comparisons)])
            
            missing_instances = gt_instances - matched_instances
            extra_instances = pred_instances - matched_instances
            
            # Average field accuracy within matched instances
            matched_comps = [c for inst in instances if inst.is_matched for c in inst.field_comparisons]
            avg_field_accuracy = (
                sum(1 for c in matched_comps if c.is_correct) / len(matched_comps)
                if matched_comps else 0.0
            )
            
            instance_recall = matched_instances / gt_instances if gt_instances > 0 else 0.0
            instance_precision = matched_instances / pred_instances if pred_instances > 0 else 0.0
            instance_f1 = (
                2 * (instance_precision * instance_recall) / (instance_precision + instance_recall)
                if (instance_precision + instance_recall) > 0 else 0.0
            )
            
            metrics[parent] = InstanceMetrics(
                total_instances=gt_instances,
                matched_instances=matched_instances,
                missing_instances=missing_instances,
                extra_instances=extra_instances,
                instance_match_rate=instance_recall,
                avg_field_accuracy_in_matched=avg_field_accuracy,
                instance_precision=instance_precision,
                instance_recall=instance_recall,
                instance_f1_score=instance_f1
            )
        
        return metrics
    
    def _calculate_field_metrics(self, comparisons: list[FieldComparison]) -> dict[str, FieldMetrics]:
        """Calculate per-field metrics."""
        field_groups: dict[str, list[FieldComparison]] = defaultdict(list)
        for comp in comparisons:
            field_groups[comp.field_name].append(comp)
        
        field_metrics = {}
        for field_name, comps in field_groups.items():
            total_gt = sum(1 for c in comps if c.ground_truth_value is not None)
            total_pred = sum(1 for c in comps if c.predicted_value is not None)
            correct = sum(1 for c in comps if c.is_correct)
            incorrect = sum(1 for c in comps if not c.is_correct and not c.is_missing and not c.is_extra)
            missing = sum(1 for c in comps if c.is_missing)
            
            accuracy = correct / total_gt if total_gt > 0 else 0.0
            precision = correct / total_pred if total_pred > 0 else 0.0
            recall = correct / total_gt if total_gt > 0 else 0.0
            
            avg_confidence = sum(c.match_result.confidence for c in comps) / len(comps) if comps else 0.0
            
            match_type_dist = {}
            for c in comps:
                match_type = c.match_result.match_type.value
                match_type_dist[match_type] = match_type_dist.get(match_type, 0) + 1
            
            field_metrics[field_name] = FieldMetrics(
                field_name=field_name,
                total_occurrences=total_gt,
                correct_predictions=correct,
                incorrect_predictions=incorrect,
                missing_predictions=missing,
                accuracy=accuracy,
                precision=precision,
                recall=recall,
                avg_confidence=avg_confidence,
                match_type_distribution=match_type_dist
            )
        
        return field_metrics


# Singleton instance
_evaluation_service: Optional[EvaluationService] = None


def get_evaluation_service() -> EvaluationService:
    """Get or create evaluation service singleton."""
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = EvaluationService()
    return _evaluation_service
