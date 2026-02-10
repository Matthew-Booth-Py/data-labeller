"""Service for evaluating extraction quality against ground truth."""

import time
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.evaluation import (
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
        evaluated_by: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> ExtractionEvaluation:
        """
        Evaluate extraction quality by comparing against ground truth annotations.

        Args:
            document_id: Document to evaluate
            prompt_version_id: Prompt version to use (None = active version)
            use_llm_refinement: Whether to use LLM refinement
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
            )
            field_evaluations.append(field_eval)

        # Calculate aggregate metrics
        metrics = self._calculate_metrics(field_evaluations)

        # Get prompt version info
        prompt_version = None
        prompt_version_name = None
        if prompt_version_id:
            prompt_version = self.sqlite_client.get_prompt_version(prompt_version_id)
            if prompt_version:
                prompt_version_name = prompt_version.name

        # Create evaluation record
        evaluation = ExtractionEvaluation(
            id=str(uuid4()),
            document_id=document_id,
            document_type_id=doc_type.id,
            prompt_version_id=prompt_version_id,
            prompt_version_name=prompt_version_name,
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

        # Group annotations by label
        annotations_by_label = {}
        for ann in annotations:
            label_name = ann.label_name or "unknown"
            if label_name not in annotations_by_label:
                annotations_by_label[label_name] = []
            annotations_by_label[label_name].append(ann)

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
        
        # Group annotations by property
        items_data = {}
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
                    
                    if prop_name not in items_data:
                        items_data[prop_name] = []
                    
                    # Parse each annotation value
                    for ann in anns:
                        value = self._parse_value(
                            ann.normalized_value or ann.text,
                            prop_schema.type.value if hasattr(prop_schema, 'type') else 'string'
                        )
                        items_data[prop_name].append(value)
        
        # Build array of objects from collected data
        # Assume all properties have the same number of items
        if not items_data:
            return []
        
        max_items = max(len(values) for values in items_data.values())
        result = []
        
        for i in range(max_items):
            item = {}
            for prop_name in properties.keys():
                if prop_name in items_data and i < len(items_data[prop_name]):
                    item[prop_name] = items_data[prop_name][i]
            if item:  # Only add if we have at least one property
                result.append(item)
        
        return result

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
    ) -> FieldEvaluation:
        """Evaluate a single field."""
        is_present = ground_truth_value is not None
        is_extracted = extracted_value is not None

        # Normalize values for comparison
        extracted_normalized = self._normalize_value(extracted_value)
        ground_truth_normalized = self._normalize_value(ground_truth_value)

        # Check if correct
        is_correct = False
        if is_present and is_extracted:
            # For complex structures (arrays of objects), use deep comparison
            if isinstance(extracted_value, list) and isinstance(ground_truth_value, list):
                is_correct = self._compare_arrays(extracted_value, ground_truth_value)
            else:
                is_correct = extracted_normalized == ground_truth_normalized

        return FieldEvaluation(
            field_name=field_name,
            extracted_value=extracted_value,
            ground_truth_value=ground_truth_value,
            is_correct=is_correct,
            is_present=is_present,
            is_extracted=is_extracted,
        )

    def _compare_arrays(self, extracted: list, ground_truth: list) -> bool:
        """Compare two arrays, handling nested objects."""
        if len(extracted) != len(ground_truth):
            return False
        
        # Normalize and compare
        extracted_normalized = self._normalize_value(extracted)
        ground_truth_normalized = self._normalize_value(ground_truth)
        
        return extracted_normalized == ground_truth_normalized

    def _normalize_value(self, value: Any) -> Any:
        """Normalize value for comparison."""
        if value is None:
            return None

        # Convert to string and normalize whitespace
        if isinstance(value, str):
            # Remove currency symbols and commas for numeric strings
            cleaned = value.strip().replace('$', '').replace(',', '')
            return cleaned.lower()

        # For dictionaries (objects), normalize each value and sort by keys
        if isinstance(value, dict):
            return {k: self._normalize_value(v) for k in sorted(value.keys()) for v in [value[k]]}

        # For lists, normalize each element
        if isinstance(value, list):
            # If list contains dicts, sort by a consistent key or convert to tuple
            if value and isinstance(value[0], dict):
                # Sort list of dicts by their normalized representation
                return sorted([
                    tuple(sorted((k, self._normalize_value(v)) for k, v in item.items()))
                    for item in value
                ])
            # For simple lists, normalize and sort
            return sorted([self._normalize_value(v) for v in value])

        # For numbers, convert to float
        if isinstance(value, (int, float)):
            return float(value)

        return value

    def _calculate_metrics(
        self, field_evaluations: list[FieldEvaluation]
    ) -> ExtractionEvaluationMetrics:
        """Calculate aggregate metrics from field evaluations."""
        total_fields = len(field_evaluations)
        correct_fields = sum(1 for f in field_evaluations if f.is_correct)
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
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            field_evaluations=field_evaluations,
        )


# Singleton instance
_evaluation_service: Optional[EvaluationService] = None


def get_evaluation_service() -> EvaluationService:
    """Get or create the evaluation service singleton."""
    global _evaluation_service
    if _evaluation_service is None:
        _evaluation_service = EvaluationService()
    return _evaluation_service
