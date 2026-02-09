"""Extraction service for converting annotations into structured data."""

import json
import re
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from openai import OpenAI

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.taxonomy import ExtractedField, ExtractionResult, SchemaField


class ExtractionService:
    """Service for extracting structured data from document annotations."""

    def __init__(self):
        self.client = OpenAI()
        self.model = "gpt-5-mini"

    def extract_from_annotations(
        self, 
        document_id: str,
        use_llm_refinement: bool = True
    ) -> ExtractionResult:
        """
        Extract structured data from a document's annotations.
        
        This maps annotations to the schema fields defined for the document type.
        Optionally uses LLM to normalize and validate extracted values.
        
        Args:
            document_id: The document to extract from
            use_llm_refinement: Whether to use LLM to refine/normalize values
            
        Returns:
            ExtractionResult with extracted field values
        """
        sqlite_client = get_sqlite_client()
        vector_store = get_vector_store()
        
        # Get document
        document = vector_store.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Get classification
        classification = sqlite_client.get_classification(document_id)
        if not classification:
            raise ValueError(f"Document {document_id} is not classified. Please classify first.")
        
        # Get document type with schema
        doc_type = sqlite_client.get_document_type(classification.document_type_id)
        if not doc_type:
            raise ValueError(f"Document type {classification.document_type_id} not found")
        
        if not doc_type.schema_fields:
            raise ValueError(f"Document type '{doc_type.name}' has no schema fields defined")
        
        # Get annotations
        annotations = sqlite_client.list_annotations(document_id=document_id)
        
        # Build initial extraction from annotations
        extracted_fields: list[ExtractedField] = []
        
        # Group annotations by label for easier mapping
        annotations_by_label: dict[str, list] = {}
        for ann in annotations:
            label_name = ann.label_name or "unknown"
            if label_name not in annotations_by_label:
                annotations_by_label[label_name] = []
            annotations_by_label[label_name].append(ann)
        
        # Map annotations to schema fields
        for field in doc_type.schema_fields:
            field_value = self._extract_field_value(field, annotations_by_label, document.content or "")
            if field_value is not None:
                extracted_fields.append(field_value)
        
        # Use LLM to refine if enabled and we have some annotations
        if use_llm_refinement and annotations:
            extracted_fields = self._refine_with_llm(
                document, doc_type.schema_fields, annotations, extracted_fields
            )
        
        result = ExtractionResult(
            document_id=document_id,
            document_type_id=doc_type.id,
            fields=extracted_fields,
            extracted_at=datetime.utcnow()
        )
        
        # Save extraction result
        self._save_extraction(result)
        
        return result

    def _extract_field_value(
        self, 
        field: SchemaField, 
        annotations_by_label: dict, 
        content: str
    ) -> Optional[ExtractedField]:
        """Extract a single field value from annotations."""
        # Try to find matching annotations by field name
        field_name_lower = field.name.lower().replace("_", " ")
        
        matching_annotations = []
        for label_name, anns in annotations_by_label.items():
            label_lower = label_name.lower().replace("_", " ")
            # Check for exact match or partial match
            if label_lower == field_name_lower or field_name_lower in label_lower or label_lower in field_name_lower:
                matching_annotations.extend(anns)
        
        if not matching_annotations:
            return None
        
        # Extract value based on field type
        if field.type.value == "array":
            # Multiple values
            values = [ann.normalized_value or ann.text for ann in matching_annotations]
            return ExtractedField(
                field_name=field.name,
                value=values,
                confidence=0.8,
                source_text="; ".join([ann.text for ann in matching_annotations[:3]])
            )
        else:
            # Single value - take the first/best match
            ann = matching_annotations[0]
            value = ann.normalized_value or ann.text
            
            # Type conversion
            if field.type.value == "number":
                try:
                    # Extract number from text
                    numbers = re.findall(r'[\d,]+\.?\d*', value)
                    if numbers:
                        value = float(numbers[0].replace(',', ''))
                except ValueError:
                    pass
            elif field.type.value == "boolean":
                value = value.lower() in ('yes', 'true', '1', 'y')
            elif field.type.value == "date":
                # Keep as string for now, could parse to ISO format
                pass
            
            return ExtractedField(
                field_name=field.name,
                value=value,
                confidence=0.8,
                source_text=ann.text
            )

    def _refine_with_llm(
        self,
        document,
        schema_fields: list[SchemaField],
        annotations,
        initial_fields: list[ExtractedField]
    ) -> list[ExtractedField]:
        """Use LLM to refine and fill in missing extracted fields."""
        
        # Build context from annotations
        annotation_context = "\n".join([
            f"- {ann.label_name}: \"{ann.text}\"" + 
            (f" (normalized: {ann.normalized_value})" if ann.normalized_value else "")
            for ann in annotations[:30]  # Limit for context
        ])
        
        # Build initial extraction context
        initial_context = "\n".join([
            f"- {f.field_name}: {json.dumps(f.value)}"
            for f in initial_fields
        ])
        
        # Build schema description
        schema_desc = "\n".join([
            f"- {f.name} ({f.type.value})" + (f": {f.description}" if f.description else "")
            for f in schema_fields
        ])
        
        # Truncate document content
        content = document.content or ""
        if len(content) > 6000:
            content = content[:3000] + "\n...[truncated]...\n" + content[-3000:]
        
        system_prompt = """You are a document extraction expert. Given annotations, initial extractions, and document content, refine the extracted field values.

Your task:
1. Validate and normalize the initial extractions
2. Fill in any missing fields that can be extracted from the document
3. Correct any obvious errors in the extracted values

Respond with a JSON object containing the refined field values:
{
    "field_name": "extracted value or null if not found",
    ...
}

For arrays, use JSON array format. For numbers, return numeric values. For dates, use ISO format when possible."""

        user_prompt = f"""## Schema Fields to Extract

{schema_desc}

## Current Annotations

{annotation_context}

## Initial Extraction (to refine)

{initial_context if initial_context else "No initial extraction - all fields need extraction"}

## Document Content

```
{content}
```

Extract/refine all schema fields. Return as JSON."""

        print(f"\n{'='*60}")
        print("EXTRACTION REFINEMENT")
        print(f"{'='*60}")
        print(f"Document: {document.filename}")
        print(f"Fields: {[f.name for f in schema_fields]}")
        print(f"{'='*60}\n")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            result_text = response.choices[0].message.content
            refined = json.loads(result_text)
            
            print(f"Refined extraction: {refined}")
            
            # Convert to ExtractedField objects
            refined_fields = []
            for field in schema_fields:
                if field.name in refined and refined[field.name] is not None:
                    # Find source from initial or annotations
                    source = None
                    for f in initial_fields:
                        if f.field_name == field.name:
                            source = f.source_text
                            break
                    
                    refined_fields.append(ExtractedField(
                        field_name=field.name,
                        value=refined[field.name],
                        confidence=0.85,
                        source_text=source
                    ))
            
            return refined_fields
            
        except Exception as e:
            print(f"LLM refinement error: {e}")
            # Fall back to initial fields
            return initial_fields

    def _save_extraction(self, result: ExtractionResult):
        """Save extraction result to database."""
        sqlite_client = get_sqlite_client()
        sqlite_client.save_extraction_result(result)


# Singleton instance
_extraction_service: Optional[ExtractionService] = None


def get_extraction_service() -> ExtractionService:
    """Get or create the extraction service singleton."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = ExtractionService()
    return _extraction_service
