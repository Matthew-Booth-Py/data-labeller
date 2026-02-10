"""Extraction service for converting annotations into structured data."""

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from openai import OpenAI

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.taxonomy import ExtractedField, ExtractionResult, SchemaField
from uu_backend.services.schema_generator import generate_pydantic_schema, schema_to_json_schema

logger = logging.getLogger(__name__)


class ExtractionService:
    """Service for extracting structured data from document annotations."""

    def __init__(self):
        self.client = OpenAI()
        self.model = "gpt-5-mini"

    def extract_structured(
        self,
        document_id: str,
        prompt_version_id: Optional[str] = None
    ) -> ExtractionResult:
        """
        Extract structured data directly from document using OpenAI structured output.
        
        This uses the schema fields to generate a Pydantic model and enforces
        structured output from the LLM, bypassing the need for annotations.
        
        Args:
            document_id: The document to extract from
            prompt_version_id: Optional prompt version to use
            
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
        
        # Generate Pydantic schema from field definitions
        ExtractionModel = generate_pydantic_schema(
            doc_type.schema_fields,
            model_name=f"{doc_type.name.replace(' ', '')}Extraction"
        )
        json_schema = schema_to_json_schema(ExtractionModel)
        
        # Truncate document content
        content = document.content or ""
        if len(content) > 8000:
            content = content[:4000] + "\n...[truncated]...\n" + content[-4000:]
        
        # Get prompt (use version if specified, otherwise default)
        system_prompt = doc_type.system_prompt or self._get_default_extraction_prompt(doc_type)
        
        if prompt_version_id:
            prompt_version = sqlite_client.get_prompt_version(prompt_version_id)
            if prompt_version:
                system_prompt = prompt_version.system_prompt
        
        user_prompt = f"""Extract structured data from the following document.

Document Type: {doc_type.name}

Document Content:
```
{content}
```

Extract all fields according to the schema. Return null for fields that cannot be found."""

        print(f"\n{'='*60}")
        print("STRUCTURED EXTRACTION")
        print(f"{'='*60}")
        print(f"Document: {document.filename}")
        print(f"Type: {doc_type.name}")
        print(f"Fields: {[f.name for f in doc_type.schema_fields]}")
        print(f"{'='*60}\n")

        try:
            response = self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",  # Structured outputs require this model
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=ExtractionModel,
            )
            
            extracted_data = response.choices[0].message.parsed
            
            print(f"Extracted: {extracted_data.model_dump()}")
            
            # Convert to ExtractedField objects
            extracted_fields = []
            for field in doc_type.schema_fields:
                value = getattr(extracted_data, field.name, None)
                if value is not None:
                    # Convert Pydantic models to dicts for storage
                    if hasattr(value, 'model_dump'):
                        value = value.model_dump()
                    elif isinstance(value, list) and value and hasattr(value[0], 'model_dump'):
                        value = [item.model_dump() for item in value]
                    
                    extracted_fields.append(ExtractedField(
                        field_name=field.name,
                        value=value,
                        confidence=0.95,  # High confidence for structured output
                        source_text=None
                    ))
            
            result = ExtractionResult(
                document_id=document_id,
                document_type_id=doc_type.id,
                fields=extracted_fields,
                schema_version_id=doc_type.schema_version_id,
                prompt_version_id=prompt_version_id,
                extracted_at=datetime.utcnow()
            )
            
            # Save extraction result
            self._save_extraction(result)
            
            return result
            
        except Exception as e:
            print(f"Structured extraction error: {e}")
            raise ValueError(f"Extraction failed: {str(e)}")

    def _get_default_extraction_prompt(self, doc_type) -> str:
        """Get default extraction prompt for a document type."""
        return f"""You are an expert at extracting structured data from {doc_type.name} documents.

Extract all fields accurately from the document. Pay special attention to:
- Tables: Extract all rows and columns
- Numbers: Remove currency symbols and commas, return as numbers
- Dates: Normalize to YYYY-MM-DD format when possible
- Arrays: Include all items found in the document

If a field cannot be found, return null. Do not make up data."""

    def extract_from_annotations(
        self, 
        document_id: str,
        use_llm_refinement: bool = True,
        prompt_version_id: Optional[str] = None
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
            logger.info(
                "Starting extraction refinement",
                extra={
                    "document_id": document_id,
                    "prompt_version_id": prompt_version_id,
                    "mode": "annotation_refinement",
                },
            )
            extracted_fields = self._refine_with_llm(
                document, doc_type.schema_fields, annotations, extracted_fields, prompt_version_id
            )
            logger.info(
                "Completed extraction refinement",
                extra={
                    "document_id": document_id,
                    "prompt_version_id": prompt_version_id,
                    "mode": "annotation_refinement",
                },
            )
        
        result = ExtractionResult(
            document_id=document_id,
            document_type_id=doc_type.id,
            fields=extracted_fields,
            schema_version_id=doc_type.schema_version_id,
            prompt_version_id=prompt_version_id,
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
        initial_fields: list[ExtractedField],
        prompt_version_id: Optional[str] = None
    ) -> list[ExtractedField]:
        """Use LLM to refine and fill in missing extracted fields."""
        sqlite_client = get_sqlite_client()
        
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
        
        # Get prompt version if specified, otherwise use default
        system_prompt = None
        user_prompt_template = None
        
        if prompt_version_id:
            prompt_version = sqlite_client.get_prompt_version(prompt_version_id)
            if prompt_version:
                system_prompt = prompt_version.system_prompt
                user_prompt_template = prompt_version.user_prompt_template
        
        # Fall back to default prompts
        if not system_prompt:
            from uu_backend.llm.prompts import EXTRACTION_SYSTEM_V1, EXTRACTION_USER_TEMPLATE_V1
            system_prompt = EXTRACTION_SYSTEM_V1
            user_prompt_template = EXTRACTION_USER_TEMPLATE_V1
        
        # Format user prompt with context
        user_prompt = user_prompt_template.format(
            schema_desc=schema_desc,
            annotation_context=annotation_context,
            initial_context=initial_context if initial_context else "No initial extraction - all fields need extraction",
            content=content
        )

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
