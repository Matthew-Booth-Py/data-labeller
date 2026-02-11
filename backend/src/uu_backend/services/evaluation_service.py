"""Service for evaluating extraction quality against ground truth."""

import difflib
import math
import re
import time
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.evaluation import (
    BenchmarkGateResult,
    BenchmarkRunResult,
    ExtractionEvaluation,
    ExtractionEvaluationMetrics,
    FieldEvaluation,
)
from uu_backend.services.extraction_service import get_extraction_service


class EvaluationService:
    """Service for evaluating extraction quality."""

    def __init__(self):
        self.extraction_service = get_extraction_service()
        self.sqlite_client = get_sqlite_client()
        self.vector_store = get_vector_store()

    def evaluate_extraction(
        self,
        document_id: str,
        prompt_version_id: Optional[str] = None,
        use_llm_refinement: bool = True,
        use_structured_output: bool = False,
        comparator_mode: str = "normalized",
        fuzzy_threshold: float = 0.85,
        evaluated_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ExtractionEvaluation:
        """
        Evaluate extraction quality by comparing against ground truth annotations.

        Args:
            document_id: Document to evaluate
            prompt_version_id: Prompt version to use (None = active version)
            use_llm_refinement: Whether to use LLM refinement (annotation-based only)
            use_structured_output: Use OpenAI structured output (bypasses annotations)
            evaluated_by: User running the evaluation
            notes: Optional notes

        Returns:
            ExtractionEvaluation with metrics
        """
        # Get document
        document = self.vector_store.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Get classification
        classification = self.sqlite_client.get_classification(document_id)
        if not classification:
            raise ValueError(f"Document {document_id} is not classified")

        # Get document type
        doc_type = self.sqlite_client.get_document_type(classification.document_type_id)
        if not doc_type:
            raise ValueError(f"Document type {classification.document_type_id} not found")

        if not doc_type.schema_fields:
            raise ValueError(f"Document type '{doc_type.name}' has no schema fields")

        # Get ground truth annotations
        annotations = self.sqlite_client.list_annotations(document_id=document_id)
        if not annotations:
            raise ValueError(
                f"Document {document_id} has no annotations. Please label it first to create ground truth."
            )

        # Build ground truth from annotations
        ground_truth = self._build_ground_truth(annotations, doc_type.schema_fields)

        # Run extraction
        start_time = time.time()
        if use_structured_output:
            extraction_result = self.extraction_service.extract_structured(
                document_id=document_id,
                prompt_version_id=prompt_version_id
            )
        else:
            extraction_result = self.extraction_service.extract_from_annotations(
                document_id=document_id, 
                use_llm_refinement=use_llm_refinement,
                prompt_version_id=prompt_version_id
            )
        extraction_time_ms = int((time.time() - start_time) * 1000)

        # Build extracted values map
        extracted_values = {field.field_name: field.value for field in extraction_result.fields}

        # Evaluate each field
        field_evaluations = []
        for field in doc_type.schema_fields:
            field_eval = self._evaluate_field(
                field_name=field.name,
                extracted_value=extracted_values.get(field.name),
                ground_truth_value=ground_truth.get(field.name),
                comparator_mode=comparator_mode,
                fuzzy_threshold=fuzzy_threshold,
            )
            field_evaluations.append(field_eval)

        # Calculate aggregate metrics
        metrics = self._calculate_metrics(field_evaluations, comparator_mode=comparator_mode)

        # Get prompt version info
        prompt_version = None
        prompt_version_name = None
        if prompt_version_id:
            prompt_version = self.sqlite_client.get_prompt_version(prompt_version_id)
            if prompt_version:
                prompt_version_name = prompt_version.name
        active_field_prompt_versions = self.sqlite_client.list_active_field_prompt_version_names(
            doc_type.id
        )
        field_prompt_versions = {
            field.name: active_field_prompt_versions.get(field.name, "0.0")
            for field in doc_type.schema_fields
        }

        # Create evaluation record
        evaluation = ExtractionEvaluation(
            id=str(uuid4()),
            document_id=document_id,
            document_type_id=doc_type.id,
            prompt_version_id=prompt_version_id,
            prompt_version_name=prompt_version_name,
            field_prompt_versions=field_prompt_versions,
            schema_version_id=doc_type.schema_version_id,
            metrics=metrics,
            extraction_time_ms=extraction_time_ms,
            evaluated_by=evaluated_by,
            evaluated_at=datetime.utcnow(),
            notes=notes,
        )

        # Save evaluation
        self.sqlite_client.save_evaluation(evaluation)

        return evaluation

    def _build_ground_truth(
        self, annotations: list, schema_fields: list
    ) -> dict[str, Any]:
        """Build ground truth values from annotations."""
        ground_truth = {}

        # Group annotations by label and sort by document position
        annotations_by_label = {}
        for ann in annotations:
            label_name = ann.label_name or "unknown"
            if label_name not in annotations_by_label:
                annotations_by_label[label_name] = []
            annotations_by_label[label_name].append(ann)
        
        # Sort each label's annotations by start_offset (document order)
        for label_name in annotations_by_label:
            annotations_by_label[label_name].sort(
                key=lambda a: a.start_offset if a.start_offset is not None else 0
            )

        # Map to schema fields
        for field in schema_fields:
            field_name_lower = field.name.lower().replace("_", " ")

            # Handle array of objects (e.g., claim_items)
            if field.type.value == "array" and field.items and field.items.type.value == "object":
                ground_truth[field.name] = self._build_array_ground_truth(
                    field, annotations_by_label
                )
            else:
                # Find matching annotations for simple fields
                matching_annotations = []
                for label_name, anns in annotations_by_label.items():
                    label_lower = label_name.lower().replace("_", " ")
                    if (
                        label_lower == field_name_lower
                        or field_name_lower in label_lower
                        or label_lower in field_name_lower
                    ):
                        matching_annotations.extend(anns)

                if matching_annotations:
                    # Extract value based on field type
                    if field.type.value == "array":
                        ground_truth[field.name] = [
                            self._parse_value(ann.normalized_value or ann.text, field.items.type.value if field.items else "string")
                            for ann in matching_annotations
                        ]
                    else:
                        # Take first annotation as ground truth
                        ann = matching_annotations[0]
                        ground_truth[field.name] = self._parse_value(
                            ann.normalized_value or ann.text, 
                            field.type.value
                        )

        return ground_truth

    def _build_array_ground_truth(
        self, field, annotations_by_label: dict
    ) -> list[dict]:
        """Build ground truth for array of objects field (e.g., claim_items)."""
        # Get the object properties from the schema
        if not field.items or not field.items.properties:
            return []
        
        properties = field.items.properties
        
        # Check if we have metadata-based key-value annotations
        # These are annotations with metadata={'key': 'prop_name'} and text contains the value
        # We need to match annotations for THIS field specifically
        field_name_lower = field.name.lower().replace("_", " ")
        metadata_annotations = []
        
        for label_name, anns in annotations_by_label.items():
            label_lower = label_name.lower().replace("_", " ")
            # Check if this label matches our field
            if label_lower == field_name_lower or field_name_lower in label_lower or label_lower in field_name_lower:
                for ann in anns:
                    if ann.metadata and 'key' in ann.metadata:
                        metadata_annotations.append(ann)
        
        # Debug logging
        print(f"[DEBUG] Field: {field.name}")
        print(f"[DEBUG] Total annotations by label: {sum(len(anns) for anns in annotations_by_label.values())}")
        print(f"[DEBUG] Metadata annotations found: {len(metadata_annotations)}")
        for ann in metadata_annotations[:5]:  # Show first 5
            print(f"[DEBUG]   - key={ann.metadata.get('key')}, text={ann.text[:50] if ann.text else None}")
        
        # If we have metadata-based annotations, use those exclusively
        if metadata_annotations:
            result = self._build_from_key_value_pairs(metadata_annotations, properties)
            print(f"[DEBUG] Built {len(result)} rows from key-value pairs")
            return result
        
        # Otherwise, fall back to the old label-based approach
        # First pass: collect all annotations with their properties
        property_annotations = {}  # {prop_name: [annotations]}
        
        for prop_name, prop_schema in properties.items():
            # Expected label name is field_name + property_name (e.g., claim_items_item_name)
            expected_label = f"{field.name}_{prop_name}"
            expected_label_lower = expected_label.lower().replace("_", " ")
            
            # Also try just the property name for backward compatibility
            prop_name_lower = prop_name.lower().replace("_", " ")
            
            # Find annotations for this property
            for label_name, anns in annotations_by_label.items():
                label_lower = label_name.lower().replace("_", " ")
                
                # Check if label matches this property (prefer exact match with field prefix)
                if (label_lower == expected_label_lower or 
                    label_lower == prop_name_lower or
                    prop_name_lower in label_lower):
                    
                    property_annotations[prop_name] = anns
                    break
        
        if not property_annotations:
            return []
        
        # Second pass: group annotations by group_id (preferred), row_index, or position
        rows_data = {}  # {row_key: {prop_name: value}}
        
        # Count how many annotations have group_id or row_index set
        total_anns = sum(len(anns) for anns in property_annotations.values())
        anns_with_group_id = sum(
            1 for anns in property_annotations.values() 
            for ann in anns if ann.group_id is not None
        )
        anns_with_row_index = sum(
            1 for anns in property_annotations.values() 
            for ann in anns if ann.row_index is not None
        )
        
        # Only use group_id/row_index if MOST annotations have it (>50%)
        # This prevents one stray annotation from breaking the entire grouping
        use_group_id = anns_with_group_id > (total_anns * 0.5)
        use_row_index = anns_with_row_index > (total_anns * 0.5)
        
        if use_group_id:
            # Use group_id for grouping (best - explicit row linking)
            for prop_name, anns in property_annotations.items():
                prop_schema = properties[prop_name]
                for ann in anns:
                    group_key = ann.group_id if ann.group_id is not None else f"ungrouped-{ann.id}"
                    
                    if group_key not in rows_data:
                        rows_data[group_key] = {}
                    
                    value = self._parse_value(
                        ann.normalized_value or ann.text,
                        prop_schema.type.value if hasattr(prop_schema, 'type') else 'string'
                    )
                    rows_data[group_key][prop_name] = value
        elif use_row_index:
            # Use row_index for grouping (fallback)
            for prop_name, anns in property_annotations.items():
                prop_schema = properties[prop_name]
                for ann in anns:
                    row_idx = ann.row_index if ann.row_index is not None else -1
                    
                    if row_idx not in rows_data:
                        rows_data[row_idx] = {}
                    
                    value = self._parse_value(
                        ann.normalized_value or ann.text,
                        prop_schema.type.value if hasattr(prop_schema, 'type') else 'string'
                    )
                    rows_data[row_idx][prop_name] = value
        else:
            # Fallback: assume annotations are in document order and group by index
            # This assumes each property has the same number of annotations in the same order
            max_count = max(len(anns) for anns in property_annotations.values())
            
            for row_idx in range(max_count):
                rows_data[row_idx] = {}
                
                for prop_name, anns in property_annotations.items():
                    if row_idx < len(anns):
                        prop_schema = properties[prop_name]
                        ann = anns[row_idx]
                        
                        value = self._parse_value(
                            ann.normalized_value or ann.text,
                            prop_schema.type.value if hasattr(prop_schema, 'type') else 'string'
                        )
                        rows_data[row_idx][prop_name] = value
        
        # Build array of objects from rows_data, sorted by row_index
        if not rows_data:
            return []
        
        result = []
        for row_idx in sorted(rows_data.keys()):
            item = rows_data[row_idx]
            if item:  # Only add if we have at least one property
                result.append(item)
        
        return result

    def _build_from_key_value_pairs(
        self, annotations: list, properties: dict
    ) -> list[dict]:
        """Build ground truth from metadata-based key-value pair annotations."""
        # Group annotations by group_id or document order
        # Each key-value pair is self-contained with metadata={'key': 'prop_name'} and text contains the value
        
        print(f"[DEBUG] _build_from_key_value_pairs called with {len(annotations)} annotations")
        
        # Collect all key-value pairs with their grouping info
        kv_pairs = []
        for ann in annotations:
            if not ann.metadata or 'key' not in ann.metadata:
                continue
            
            key = ann.metadata['key']
            value = ann.text  # The actual value is in the text field
            
            print(f"[DEBUG] Processing: key={key}, value={value}, offset={ann.start_offset}")
            
            # Determine which property this belongs to
            prop_schema = None
            for prop_name, schema in properties.items():
                if prop_name == key or prop_name.lower() == key.lower():
                    prop_schema = schema
                    break
            
            if not prop_schema:
                continue  # Skip if key doesn't match any property
            
            kv_pairs.append({
                'key': key,
                'value': value,
                'group_id': ann.group_id,
                'row_index': ann.row_index,
                'start_offset': ann.start_offset or 0,
                'prop_schema': prop_schema,
            })
        
        if not kv_pairs:
            print("[DEBUG] No kv_pairs found!")
            return []
        
        print(f"[DEBUG] Collected {len(kv_pairs)} kv_pairs")
        
        # Group by group_id if most have it, otherwise by row_index, otherwise by proximity
        has_group_id = sum(1 for kv in kv_pairs if kv['group_id'] is not None)
        has_row_index = sum(1 for kv in kv_pairs if kv['row_index'] is not None)
        
        print(f"[DEBUG] has_group_id={has_group_id}, has_row_index={has_row_index}, total={len(kv_pairs)}")
        
        rows_data = {}  # {row_key: {prop_name: value}}
        
        if has_group_id > len(kv_pairs) * 0.5:
            # Group by group_id
            for kv in kv_pairs:
                group_key = kv['group_id'] if kv['group_id'] else f"ungrouped-{kv['start_offset']}"
                if group_key not in rows_data:
                    rows_data[group_key] = {}
                
                parsed_value = self._parse_value(
                    kv['value'],
                    kv['prop_schema'].type.value if hasattr(kv['prop_schema'], 'type') else 'string'
                )
                rows_data[group_key][kv['key']] = parsed_value
        
        elif has_row_index > len(kv_pairs) * 0.5:
            # Group by row_index
            for kv in kv_pairs:
                row_idx = kv['row_index'] if kv['row_index'] is not None else -1
                if row_idx not in rows_data:
                    rows_data[row_idx] = {}
                
                parsed_value = self._parse_value(
                    kv['value'],
                    kv['prop_schema'].type.value if hasattr(kv['prop_schema'], 'type') else 'string'
                )
                rows_data[row_idx][kv['key']] = parsed_value
        
        else:
            # Group by detecting when we see a duplicate key (indicates new row)
            # Sort by start_offset to process in document order
            kv_pairs.sort(key=lambda x: x['start_offset'])
            
            current_row = {}
            row_idx = 0
            seen_keys = set()
            
            for kv in kv_pairs:
                key = kv['key']
                
                # If we've seen this key before in the current row, start a new row
                if key in seen_keys:
                    # Save the current row
                    if current_row:
                        rows_data[row_idx] = current_row
                        row_idx += 1
                    # Start new row
                    current_row = {}
                    seen_keys = set()
                
                # Add this key-value pair to the current row
                parsed_value = self._parse_value(
                    kv['value'],
                    kv['prop_schema'].type.value if hasattr(kv['prop_schema'], 'type') else 'string'
                )
                current_row[key] = parsed_value
                seen_keys.add(key)
            
            # Add the last row
            if current_row:
                rows_data[row_idx] = current_row
        
        # Convert to list of dicts
        result = []
        for row_key in sorted(rows_data.keys()):
            item = rows_data[row_key]
            if item:
                result.append(item)
        
        return result

    def _is_placeholder_value(self, value: Any) -> bool:
        """Check if a value is a placeholder (TBD, N/A, etc.) that shouldn't be evaluated."""
        if value is None:
            return False
        
        value_str = str(value).strip().upper()
        placeholders = ['TBD', 'N/A', 'NA', 'UNKNOWN', 'PENDING', 'TBA', 'TO BE DETERMINED', 
                       'NOT AVAILABLE', 'NOT APPLICABLE', '--', '---', 'NULL']
        
        return value_str in placeholders

    def _parse_value(self, value: str, field_type: str) -> Any:
        """Parse a string value according to field type."""
        if value is None:
            return None
        
        value = str(value).strip()
        
        if field_type == "number":
            # Remove currency symbols and commas
            cleaned = value.replace('$', '').replace(',', '').strip()
            try:
                return float(cleaned)
            except ValueError:
                return value
        elif field_type == "boolean":
            return value.lower() in ('yes', 'true', '1', 'y')
        else:
            return value

    def _evaluate_field(
        self,
        field_name: str,
        extracted_value: Any,
        ground_truth_value: Any,
        comparator_mode: str = "normalized",
        fuzzy_threshold: float = 0.85,
    ) -> FieldEvaluation:
        """Evaluate a single field."""
        is_present = ground_truth_value is not None
        is_extracted = extracted_value is not None

        # Check if correct and calculate R² for numerical fields
        is_correct = False
        r2_score = None
        reason_code = "match"
        comparison_score = None
        
        if not is_present and not is_extracted:
            reason_code = "abstained"
        elif is_present and not is_extracted:
            reason_code = "missing_extraction"
        elif not is_present and is_extracted:
            reason_code = "extra_extraction"
        elif is_present and is_extracted:
            # For complex structures (arrays of objects), use deep comparison
            if isinstance(extracted_value, list) and isinstance(ground_truth_value, list):
                is_correct = self._compare_arrays(extracted_value, ground_truth_value)
                comparison_score = 1.0 if is_correct else 0.0
                
                # Calculate R² for arrays of objects with numerical fields
                r2_score = self._calculate_r2_for_array(extracted_value, ground_truth_value)
            else:
                is_correct, comparison_score = self._compare_values(
                    extracted_value=extracted_value,
                    ground_truth_value=ground_truth_value,
                    comparator_mode=comparator_mode,
                    fuzzy_threshold=fuzzy_threshold,
                )
            reason_code = "match" if is_correct else "value_mismatch"

        return FieldEvaluation(
            field_name=field_name,
            extracted_value=extracted_value,
            ground_truth_value=ground_truth_value,
            is_correct=is_correct,
            is_present=is_present,
            is_extracted=is_extracted,
            r2_score=r2_score,
            comparator_mode=comparator_mode,
            comparison_score=comparison_score,
            reason_code=reason_code,
        )

    def _compare_arrays(self, extracted: list, ground_truth: list) -> bool:
        """
        Compare two arrays, handling nested objects.
        For arrays of objects, use item-by-item comparison with partial credit.
        """
        # If both are empty, they match
        if not extracted and not ground_truth:
            return True
        
        # If one is empty and the other isn't, they don't match
        if not extracted or not ground_truth:
            return False
        
        # For arrays of objects, compare item-by-item after sorting by primary key
        if isinstance(extracted[0], dict) and isinstance(ground_truth[0], dict):
            # Find primary key
            primary_keys = ['id', 'name', 'item', 'item_name', 'claim_item', 'title', 'key']
            sort_key = None
            
            for key in primary_keys:
                if all(key in item for item in extracted) and all(key in item for item in ground_truth):
                    sort_key = key
                    break
            
            # Sort both arrays by primary key
            if sort_key:
                extracted_sorted = sorted(extracted, key=lambda x: str(x.get(sort_key, '')).lower())
                ground_truth_sorted = sorted(ground_truth, key=lambda x: str(x.get(sort_key, '')).lower())
            else:
                extracted_sorted = extracted
                ground_truth_sorted = ground_truth
            
            # Compare items by matching on primary key
            # This allows partial credit even when lengths differ
            matching_items = 0
            evaluable_items = 0  # Items that should be evaluated (not placeholders)
            
            if sort_key:
                # Match by primary key
                extracted_map = {str(item.get(sort_key, '')).lower(): item for item in extracted_sorted}
                ground_truth_map = {str(item.get(sort_key, '')).lower(): item for item in ground_truth_sorted}
                
                # Check all keys from both maps
                all_keys = set(extracted_map.keys()) | set(ground_truth_map.keys())
                
                for key in all_keys:
                    ext_item = extracted_map.get(key)
                    gt_item = ground_truth_map.get(key)
                    
                    # Check if ground truth item has placeholder values
                    if gt_item:
                        has_placeholder = any(self._is_placeholder_value(v) for v in gt_item.values())
                        if has_placeholder:
                            # Skip items with placeholder values - they shouldn't be evaluated
                            continue
                    
                    evaluable_items += 1
                    
                    if ext_item and gt_item:
                        # Both exist - compare them
                        ext_normalized = self._normalize_value(ext_item)
                        gt_normalized = self._normalize_value(gt_item)
                        
                        if ext_normalized == gt_normalized:
                            matching_items += 1
                    elif not ext_item and not gt_item:
                        # Neither exists - this shouldn't happen but count as match
                        matching_items += 1
            else:
                # No primary key - compare by position
                for ext_item, gt_item in zip(extracted_sorted, ground_truth_sorted):
                    # Check if ground truth item has placeholder values
                    if isinstance(gt_item, dict):
                        has_placeholder = any(self._is_placeholder_value(v) for v in gt_item.values())
                        if has_placeholder:
                            continue
                    
                    evaluable_items += 1
                    ext_normalized = self._normalize_value(ext_item)
                    gt_normalized = self._normalize_value(gt_item)
                    
                    if ext_normalized == gt_normalized:
                        matching_items += 1
            
            # Consider it correct if at least 80% of evaluable items match exactly
            # This gives partial credit for mostly-correct arrays
            # Use evaluable_items instead of total_items to exclude placeholders
            match_ratio = matching_items / evaluable_items if evaluable_items > 0 else 1.0
            return match_ratio >= 0.8
        
        # For simple arrays, use exact comparison after normalization
        extracted_normalized = self._normalize_value(extracted)
        ground_truth_normalized = self._normalize_value(ground_truth)
        
        return extracted_normalized == ground_truth_normalized

    def _compare_values(
        self,
        extracted_value: Any,
        ground_truth_value: Any,
        comparator_mode: str,
        fuzzy_threshold: float,
    ) -> tuple[bool, float]:
        """Compare two values using exact, normalized, or fuzzy semantics."""
        if comparator_mode == "exact":
            score = 1.0 if extracted_value == ground_truth_value else 0.0
            return score == 1.0, score

        extracted_normalized = self._normalize_value(extracted_value)
        ground_truth_normalized = self._normalize_value(ground_truth_value)

        if comparator_mode == "normalized":
            if extracted_normalized == ground_truth_normalized:
                return True, 1.0

            # Date-aware equivalence for differently formatted but same date strings.
            if isinstance(extracted_value, str) and isinstance(ground_truth_value, str):
                extracted_date = self._parse_date_literal(extracted_value)
                ground_truth_date = self._parse_date_literal(ground_truth_value)
                if extracted_date and ground_truth_date and extracted_date == ground_truth_date:
                    return True, 1.0

                # Free-text soft match: lexical/ordering differences shouldn't be hard-fail.
                similarity = self._text_similarity(extracted_value, ground_truth_value)
                if similarity >= 0.92:
                    return True, similarity
                return False, similarity

            return False, 0.0

        # fuzzy mode: exact on non-strings, similarity on strings
        if isinstance(extracted_normalized, str) and isinstance(ground_truth_normalized, str):
            similarity = difflib.SequenceMatcher(
                a=extracted_normalized, b=ground_truth_normalized
            ).ratio()
            return similarity >= fuzzy_threshold, similarity

        score = 1.0 if extracted_normalized == ground_truth_normalized else 0.0
        return score == 1.0, score

    def _calculate_r2_for_array(self, extracted: list, ground_truth: list) -> Optional[float]:
        """
        Calculate R² score for arrays of objects with numerical fields.
        Returns R² score for numerical fields, or None if no numerical fields found.
        """
        if not extracted or not ground_truth:
            return None
        
        # Only works for arrays of objects
        if not (isinstance(extracted[0], dict) and isinstance(ground_truth[0], dict)):
            return None
        
        # Find primary key for matching
        primary_keys = ['id', 'name', 'item', 'item_name', 'claim_item', 'title', 'key']
        sort_key = None
        
        for key in primary_keys:
            if all(key in item for item in extracted) and all(key in item for item in ground_truth):
                sort_key = key
                break
        
        if not sort_key:
            return None
        
        # Create maps by primary key
        extracted_map = {str(item[sort_key]).lower(): item for item in extracted}
        ground_truth_map = {str(item[sort_key]).lower(): item for item in ground_truth}
        
        # Find common keys (items present in both)
        common_keys = set(extracted_map.keys()) & set(ground_truth_map.keys())
        
        if not common_keys:
            return None
        
        # Collect all numerical field values
        y_true_all = []
        y_pred_all = []
        
        for key in common_keys:
            ext_item = extracted_map[key]
            gt_item = ground_truth_map[key]
            
            # Find numerical fields
            for field_name in gt_item.keys():
                if field_name == sort_key:
                    continue
                
                gt_value = gt_item.get(field_name)
                ext_value = ext_item.get(field_name)
                
                # Check if both values are numerical
                try:
                    gt_num = float(gt_value) if gt_value is not None else None
                    ext_num = float(ext_value) if ext_value is not None else None
                    
                    if gt_num is not None and ext_num is not None:
                        y_true_all.append(gt_num)
                        y_pred_all.append(ext_num)
                except (ValueError, TypeError):
                    # Not a numerical field, skip
                    continue
        
        # Need at least 2 data points to calculate R²
        if len(y_true_all) < 2:
            return None
        
        # Calculate R² score
        # R² = 1 - (SS_res / SS_tot)
        # SS_res = sum of squared residuals
        # SS_tot = total sum of squares
        
        import numpy as np
        
        y_true = np.array(y_true_all)
        y_pred = np.array(y_pred_all)
        
        # Mean of ground truth
        y_mean = np.mean(y_true)
        
        # Total sum of squares
        ss_tot = np.sum((y_true - y_mean) ** 2)
        
        # Residual sum of squares
        ss_res = np.sum((y_true - y_pred) ** 2)
        
        # R² score
        if ss_tot == 0:
            # If all ground truth values are the same, R² is undefined
            # Return 1.0 if predictions match, 0.0 otherwise
            return 1.0 if ss_res == 0 else 0.0
        
        r2 = 1 - (ss_res / ss_tot)
        
        return float(r2)

    def _normalize_value(self, value: Any) -> Any:
        """Normalize value for comparison."""
        if value is None:
            return None

        # Convert to string and normalize whitespace
        if isinstance(value, str):
            stripped = value.strip()
            # Normalize date strings to ISO for robust comparison.
            parsed_date = self._parse_date_literal(stripped)
            if parsed_date:
                return parsed_date
            # Remove currency symbols and commas for numeric strings
            cleaned = stripped.replace('$', '').replace(',', '')
            return cleaned.lower()

        # For dictionaries (objects), normalize each value and sort by keys
        if isinstance(value, dict):
            return {k: self._normalize_value(v) for k in sorted(value.keys()) for v in [value[k]]}

        # For lists, normalize each element
        if isinstance(value, list):
            # If list contains dicts, sort by a consistent key or convert to tuple
            if value and isinstance(value[0], dict):
                # Try to find a primary key field to sort by (common patterns)
                primary_keys = ['id', 'name', 'item', 'item_name', 'claim_item', 'title', 'key']
                sort_key = None
                
                # Find the first primary key that exists in all items
                for key in primary_keys:
                    if all(key in item for item in value):
                        sort_key = key
                        break
                
                # If we found a primary key, sort by it and normalize each item
                if sort_key:
                    sorted_items = sorted(value, key=lambda x: str(self._normalize_value(x.get(sort_key, ''))))
                    return [
                        {k: self._normalize_value(v) for k in sorted(item.keys()) for v in [item[k]]}
                        for item in sorted_items
                    ]
                else:
                    # Fallback: sort by the full tuple representation
                    # Convert to strings to handle mixed types
                    try:
                        return sorted([
                            tuple(sorted((k, self._normalize_value(v)) for k, v in item.items()))
                            for item in value
                        ])
                    except TypeError:
                        # If comparison fails due to mixed types, convert tuples to strings
                        return sorted([
                            tuple(sorted((k, self._normalize_value(v)) for k, v in item.items()))
                            for item in value
                        ], key=lambda x: str(x))
            # For simple lists, normalize and sort
            # Convert to strings for sorting to avoid type comparison issues
            normalized = [self._normalize_value(v) for v in value]
            try:
                return sorted(normalized)
            except TypeError:
                # If values are mixed types, convert to strings for comparison
                return sorted(normalized, key=lambda x: str(x))

        # For numbers, convert to float
        if isinstance(value, (int, float)):
            return float(value)

        return value

    def _parse_date_literal(self, value: str) -> Optional[str]:
        """Parse common date string formats and return ISO date if parseable."""
        if not value:
            return None
        s = value.strip()
        # Fast-path ISO date
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return s
        formats = (
            "%B %d, %Y",   # February 3, 2024
            "%b %d, %Y",   # Feb 3, 2024
            "%m/%d/%Y",    # 02/03/2024
            "%m-%d-%Y",    # 02-03-2024
            "%Y/%m/%d",    # 2024/02/03
            "%Y.%m.%d",    # 2024.02.03
        )
        for fmt in formats:
            try:
                return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return None

    def _text_similarity(self, a: str, b: str) -> float:
        """Compute robust similarity for free-text field evaluation."""
        a_norm = self._canonicalize_text(a)
        b_norm = self._canonicalize_text(b)
        if not a_norm and not b_norm:
            return 1.0
        if not a_norm or not b_norm:
            return 0.0

        seq_ratio = difflib.SequenceMatcher(a=a_norm, b=b_norm).ratio()
        a_tokens = a_norm.split()
        b_tokens = b_norm.split()
        a_set = set(a_tokens)
        b_set = set(b_tokens)
        overlap = len(a_set & b_set)
        precision = overlap / len(a_set) if a_set else 0.0
        recall = overlap / len(b_set) if b_set else 0.0
        token_f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) else 0.0

        return max(seq_ratio, token_f1)

    def _canonicalize_text(self, value: str) -> str:
        """Lowercase + punctuation/whitespace normalization for soft text matching."""
        lowered = value.lower()
        # Keep alnum/space only to ignore punctuation-only differences.
        cleaned = re.sub(r"[^a-z0-9\s]+", " ", lowered)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    def _calculate_metrics(
        self, field_evaluations: list[FieldEvaluation], comparator_mode: str = "normalized"
    ) -> ExtractionEvaluationMetrics:
        """Calculate aggregate metrics from field evaluations."""
        total_fields = len(field_evaluations)
        correct_fields = sum(1 for f in field_evaluations if f.is_correct)
        abstained_fields = sum(1 for f in field_evaluations if f.reason_code == "abstained")
        unsupported_fields = sum(1 for f in field_evaluations if f.reason_code == "unsupported_type")
        incorrect_fields = sum(
            1 for f in field_evaluations if f.is_extracted and f.is_present and not f.is_correct
        )
        missing_fields = sum(
            1 for f in field_evaluations if f.is_present and not f.is_extracted
        )
        extra_fields = sum(
            1 for f in field_evaluations if f.is_extracted and not f.is_present
        )

        # Calculate metrics
        accuracy = correct_fields / total_fields if total_fields > 0 else 0.0

        # Precision: correct / (correct + incorrect + extra)
        extracted_count = correct_fields + incorrect_fields + extra_fields
        precision = correct_fields / extracted_count if extracted_count > 0 else 0.0

        # Recall: correct / (correct + missing)
        present_count = correct_fields + incorrect_fields + missing_fields
        recall = correct_fields / present_count if present_count > 0 else 0.0

        # F1 score
        if precision + recall > 0:
            f1_score = 2 * (precision * recall) / (precision + recall)
        else:
            f1_score = 0.0

        return ExtractionEvaluationMetrics(
            total_fields=total_fields,
            correct_fields=correct_fields,
            incorrect_fields=incorrect_fields,
            missing_fields=missing_fields,
            extra_fields=extra_fields,
            abstained_fields=abstained_fields,
            unsupported_fields=unsupported_fields,
            comparator_mode=comparator_mode,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            field_evaluations=field_evaluations,
        )

    def evaluate_project(
        self,
        document_type_id: str,
        prompt_version_id: Optional[str] = None,
        use_llm_refinement: bool = True,
        use_structured_output: bool = False,
        comparator_mode: str = "normalized",
        fuzzy_threshold: float = 0.85,
        evaluated_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> list[ExtractionEvaluation]:
        """
        Evaluate all labeled documents in a project (document type).

        Args:
            document_type_id: Document type to evaluate
            prompt_version_id: Prompt version to use (None = active version)
            use_llm_refinement: Whether to use LLM refinement (annotation-based only)
            use_structured_output: Use OpenAI structured output (bypasses annotations)
            evaluated_by: User running the evaluation
            notes: Optional notes

        Returns:
            List of ExtractionEvaluation results for each document
        """
        # Get all document IDs with this document type
        document_ids = self.sqlite_client.get_documents_by_type(document_type_id)
        
        if not document_ids:
            raise ValueError(f"No documents found for document type {document_type_id}")

        evaluations = []
        errors = []

        for document_id in document_ids:
            try:
                # Check if document has annotations
                annotations = self.sqlite_client.list_annotations(
                    document_id=document_id
                )
                if not annotations:
                    print(f"Skipping document {document_id} - no annotations")
                    continue  # Skip documents without annotations

                # Run evaluation for this document
                evaluation = self.evaluate_extraction(
                    document_id=document_id,
                    prompt_version_id=prompt_version_id,
                    use_llm_refinement=use_llm_refinement,
                    use_structured_output=use_structured_output,
                    comparator_mode=comparator_mode,
                    fuzzy_threshold=fuzzy_threshold,
                    evaluated_by=evaluated_by,
                    notes=notes,
                )
                evaluations.append(evaluation)
                print(f"✓ Evaluated document {document_id}")
            except Exception as e:
                print(f"✗ Failed to evaluate document {document_id}: {str(e)}")
                import traceback
                traceback.print_exc()
                errors.append({
                    "document_id": document_id,
                    "error": str(e)
                })

        if not evaluations and errors:
            raise ValueError(
                f"Failed to evaluate any documents. Errors: {errors}"
            )

        return evaluations

    def evaluate_benchmark(
        self,
        dataset_id: str,
        prompt_version_id: Optional[str] = None,
        baseline_run_id: Optional[str] = None,
        use_llm_refinement: bool = True,
        use_structured_output: bool = False,
        comparator_mode: str = "normalized",
        fuzzy_threshold: float = 0.85,
        evaluated_by: Optional[str] = None,
        notes: Optional[str] = None,
        required_field_gates: Optional[dict[str, dict[str, float]]] = None,
    ) -> BenchmarkRunResult:
        """Run benchmark evaluation over a dataset split and persist run summary."""
        dataset = self.sqlite_client.get_benchmark_dataset(dataset_id)
        if not dataset:
            raise ValueError(f"Benchmark dataset {dataset_id} not found")
        if not dataset["documents"]:
            raise ValueError(f"Benchmark dataset {dataset_id} has no documents")

        evaluations: list[ExtractionEvaluation] = []
        split_evaluations: dict[str, list[ExtractionEvaluation]] = {}
        subtype_evaluations: dict[str, list[ExtractionEvaluation]] = {}
        errors: list[dict[str, str]] = []

        for assignment in dataset["documents"]:
            document_id = assignment["document_id"]
            split = assignment.get("split") or "test"
            subtype = assignment.get("doc_subtype") or "unknown"
            try:
                evaluation = self.evaluate_extraction(
                    document_id=document_id,
                    prompt_version_id=prompt_version_id,
                    use_llm_refinement=use_llm_refinement,
                    use_structured_output=use_structured_output,
                    comparator_mode=comparator_mode,
                    fuzzy_threshold=fuzzy_threshold,
                    evaluated_by=evaluated_by,
                    notes=notes,
                )
                evaluations.append(evaluation)
                split_evaluations.setdefault(split, []).append(evaluation)
                subtype_evaluations.setdefault(subtype, []).append(evaluation)
            except Exception as exc:
                errors.append({"document_id": document_id, "error": str(exc)})

        if not evaluations:
            raise ValueError(
                f"Benchmark evaluation failed for all documents in dataset {dataset_id}: {errors}"
            )

        overall_metrics = self._aggregate_eval_metrics(evaluations)
        split_metrics = {
            split: self._aggregate_eval_metrics(eval_list)
            for split, eval_list in split_evaluations.items()
        }
        subtype_scorecards = {
            subtype: self._aggregate_field_scorecard(eval_list)
            for subtype, eval_list in subtype_evaluations.items()
        }
        confidence_intervals = self._compute_metric_confidence_intervals(evaluations)
        gate_results = self._evaluate_quality_gates(evaluations, required_field_gates or {})
        passed_gates = all(g.passed for g in gate_results)

        drift_delta = None
        if baseline_run_id:
            baseline = self.sqlite_client.get_benchmark_run(baseline_run_id)
            if baseline:
                drift_delta = {
                    metric: overall_metrics[metric] - baseline["overall_metrics"].get(metric, 0.0)
                    for metric in ("accuracy", "precision", "recall", "f1_score")
                }

        run = BenchmarkRunResult(
            id=str(uuid4()),
            dataset_id=dataset_id,
            document_type_id=dataset["document_type_id"],
            prompt_version_id=prompt_version_id,
            baseline_run_id=baseline_run_id,
            total_documents=len(dataset["documents"]),
            successful_documents=len(evaluations),
            failed_documents=len(errors),
            overall_metrics=overall_metrics,
            split_metrics=split_metrics,
            subtype_scorecards=subtype_scorecards,
            confidence_intervals=confidence_intervals,
            drift_delta=drift_delta,
            gate_results=gate_results,
            passed_gates=passed_gates,
            errors=errors,
            evaluated_by=evaluated_by,
            created_at=datetime.utcnow(),
            notes=notes,
        )

        self.sqlite_client.save_benchmark_run(
            {
                **run.model_dump(),
                "created_at": run.created_at,
                "use_llm_refinement": use_llm_refinement,
                "use_structured_output": use_structured_output,
            }
        )
        return run

    def _aggregate_eval_metrics(self, evaluations: list[ExtractionEvaluation]) -> dict[str, float]:
        """Aggregate top-level metrics over multiple evaluations."""
        total = len(evaluations)
        if total == 0:
            return {"accuracy": 0.0, "precision": 0.0, "recall": 0.0, "f1_score": 0.0}
        return {
            "accuracy": sum(e.metrics.accuracy for e in evaluations) / total,
            "precision": sum(e.metrics.precision for e in evaluations) / total,
            "recall": sum(e.metrics.recall for e in evaluations) / total,
            "f1_score": sum(e.metrics.f1_score for e in evaluations) / total,
        }

    def _aggregate_field_scorecard(
        self, evaluations: list[ExtractionEvaluation]
    ) -> dict[str, dict[str, float]]:
        """Build per-field scorecard for a group of evaluations."""
        stats: dict[str, dict[str, int]] = {}
        for evaluation in evaluations:
            for field_eval in evaluation.metrics.field_evaluations:
                field_stats = stats.setdefault(
                    field_eval.field_name,
                    {"correct": 0, "present": 0, "extracted": 0, "total": 0},
                )
                field_stats["total"] += 1
                if field_eval.is_correct:
                    field_stats["correct"] += 1
                if field_eval.is_present:
                    field_stats["present"] += 1
                if field_eval.is_extracted:
                    field_stats["extracted"] += 1

        scorecard: dict[str, dict[str, float]] = {}
        for field_name, field_stats in stats.items():
            precision = (
                field_stats["correct"] / field_stats["extracted"]
                if field_stats["extracted"] > 0
                else 0.0
            )
            recall = (
                field_stats["correct"] / field_stats["present"]
                if field_stats["present"] > 0
                else 0.0
            )
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
            scorecard[field_name] = {
                "accuracy": field_stats["correct"] / field_stats["total"] if field_stats["total"] > 0 else 0.0,
                "precision": precision,
                "recall": recall,
                "f1_score": f1,
            }
        return scorecard

    def _compute_metric_confidence_intervals(
        self, evaluations: list[ExtractionEvaluation]
    ) -> dict[str, dict[str, float]]:
        """Compute approximate 95% CI for top-level metrics over runs."""
        intervals = {}
        metric_names = ("accuracy", "precision", "recall", "f1_score")
        n = len(evaluations)
        for metric in metric_names:
            values = [getattr(e.metrics, metric) for e in evaluations]
            mean = sum(values) / n
            if n < 2:
                intervals[metric] = {"mean": mean, "lower_95": mean, "upper_95": mean}
                continue
            variance = sum((v - mean) ** 2 for v in values) / (n - 1)
            stderr = math.sqrt(variance / n)
            margin = 1.96 * stderr
            intervals[metric] = {
                "mean": mean,
                "lower_95": max(0.0, mean - margin),
                "upper_95": min(1.0, mean + margin),
            }
        return intervals

    def _evaluate_quality_gates(
        self,
        evaluations: list[ExtractionEvaluation],
        required_field_gates: dict[str, dict[str, float]],
    ) -> list[BenchmarkGateResult]:
        """Evaluate pass/fail gates for required fields."""
        field_scorecard = self._aggregate_field_scorecard(evaluations)
        results: list[BenchmarkGateResult] = []
        for field_name, thresholds in required_field_gates.items():
            actual = field_scorecard.get(
                field_name, {"f1_score": 0.0, "recall": 0.0}
            )
            min_f1 = thresholds.get("min_f1")
            min_recall = thresholds.get("min_recall")
            passed = True
            if min_f1 is not None and actual["f1_score"] < min_f1:
                passed = False
            if min_recall is not None and actual["recall"] < min_recall:
                passed = False
            results.append(
                BenchmarkGateResult(
                    field_name=field_name,
                    min_f1=min_f1,
                    min_recall=min_recall,
                    actual_f1=actual["f1_score"],
                    actual_recall=actual["recall"],
                    passed=passed,
                )
            )
        return results


# Singleton instance
_evaluation_service: Optional[EvaluationService] = None


def get_evaluation_service() -> EvaluationService:
    """Get or create the evaluation service singleton."""
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = EvaluationService()
    return _evaluation_service
