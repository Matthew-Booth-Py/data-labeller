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
        extraction_start = time.time()
        if run_extraction:
            import asyncio
            from concurrent.futures import ThreadPoolExecutor
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                extraction = await loop.run_in_executor(
                    executor,
                    self.extraction_service.extract_structured,
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
        
        # 6. Calculate metrics
        logger.info("[EVAL] Step 6: Calculating metrics...")
        metrics = self._calculate_metrics(field_comparisons)
        
        evaluation_time_ms = (time.time() - start_time) * 1000
        logger.info(f"[EVAL] Evaluation completed in {evaluation_time_ms:.2f}ms, accuracy={metrics.flattened.accuracy:.2%}")
        
        return EvaluationResult(
            document_id=document_id,
            metrics=metrics,
            field_comparisons=field_comparisons,
            instance_comparisons={},
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
        return await sync_to_async(self.extraction_service.extract_structured)(document_id)
    
    def _build_comparison_schema(
        self,
        ground_truth: list[dict],
        extraction: Any
    ) -> dict[str, dict]:
        """
        Build comparison schema grouping GT and predictions by field.
        
        Returns:
            {
                "field_name": {
                    "ground_truth": [{"value": x, "instance": 1}, ...],
                    "predicted": [{"value": y, "instance": 1}, ...]
                }
            }
        """
        schema = defaultdict(lambda: {"ground_truth": [], "predicted": []})
        
        # Add ground truth values
        for gt in ground_truth:
            field_name = gt["field_name"]
            schema[field_name]["ground_truth"].append({
                "value": gt["value"],
                "instance": gt.get("instance_num")
            })
        
        # Add predicted values (flatten nested structures)
        for extracted_field in extraction.fields:
            self._flatten_to_schema(
                extracted_field.field_name,
                extracted_field.value,
                schema
            )
        
        return dict(schema)
    
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
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                result = await loop.run_in_executor(
                    executor,
                    self.openai_client.complete_json,
                    prompt,
                    4000  # max_tokens
                )
            
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
    
    def _fallback_exact_match(self, comparison_schema: dict) -> dict:
        """Fallback to simple exact matching if LLM fails."""
        evaluations = {}
        
        for field_name, data in comparison_schema.items():
            gt_values = [item["value"] for item in data["ground_truth"]]
            pred_values = [item["value"] for item in data["predicted"]]
            
            matches = []
            matched_gt = set()
            matched_pred = set()
            
            # Simple exact match
            for gt_idx, gt_val in enumerate(gt_values):
                for pred_idx, pred_val in enumerate(pred_values):
                    if pred_idx in matched_pred:
                        continue
                    if str(gt_val).strip().lower() == str(pred_val).strip().lower():
                        matches.append({
                            "gt_idx": gt_idx,
                            "pred_idx": pred_idx,
                            "is_match": True,
                            "confidence": 1.0,
                            "reason": "Exact match"
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
    
    def _calculate_metrics(self, comparisons: list[FieldComparison]) -> EvaluationMetrics:
        """Calculate evaluation metrics."""
        flattened = self._calculate_flattened_metrics(comparisons)
        field_metrics = self._calculate_field_metrics(comparisons)
        
        return EvaluationMetrics(
            flattened=flattened,
            instance_metrics={},
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
