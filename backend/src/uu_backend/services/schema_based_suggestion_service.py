"""Schema-based annotation suggestion service using structured output."""

import re
from typing import Optional
from openai import OpenAI
from pydantic import BaseModel, Field

from uu_backend.config import get_settings
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.llm.options import reasoning_options_for_model
from uu_backend.models.annotation import AnnotationCreate, AnnotationType
from uu_backend.repositories import get_repository
from uu_backend.services.schema_generator import generate_pydantic_schema


class TextSpan(BaseModel):
    """A text span with start/end positions."""
    text: str = Field(..., description="The exact text from the document")
    start_char: int = Field(..., description="Start character position")
    end_char: int = Field(..., description="End character position")


class FieldAnnotationSuggestion(BaseModel):
    """Suggested annotation for a single field."""
    field_name: str = Field(..., description="Name of the field")
    label_name: str = Field(..., description="Label to use for annotation")
    spans: list[TextSpan] = Field(..., description="Text spans to annotate")
    confidence: float = Field(..., description="Confidence score 0-1")
    reasoning: Optional[str] = Field(None, description="Why this was suggested")
    metadata: Optional[dict] = Field(None, description="Structured metadata (e.g., key-value pairs)")


class SchemaBasedSuggestionResponse(BaseModel):
    """Response containing schema-based annotation suggestions."""
    document_id: str
    document_type_id: str
    suggestions: list[FieldAnnotationSuggestion]
    extraction_preview: dict  # Preview of what would be extracted


class SchemaBasedSuggestionService:
    """Service for suggesting annotations based on schema fields using structured output."""

    def __init__(self):
        settings = get_settings()
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_tagging_model or settings.openai_model
        self.repository = get_repository()
        self.document_repo = get_document_repository()

    def _find_text_spans(
        self,
        content: str,
        raw_value: object,
        max_matches: int = 3,
    ) -> list[TextSpan]:
        """Deterministically locate value spans in content."""
        if raw_value is None:
            return []

        value = str(raw_value).strip()
        if not value:
            return []

        spans: list[TextSpan] = []

        # First pass: exact case-sensitive matching.
        start = 0
        while len(spans) < max_matches:
            idx = content.find(value, start)
            if idx == -1:
                break
            spans.append(TextSpan(text=content[idx:idx + len(value)], start_char=idx, end_char=idx + len(value)))
            start = idx + len(value)

        # Second pass: case-insensitive regex if exact match fails.
        if not spans:
            pattern = re.escape(value)
            for m in re.finditer(pattern, content, flags=re.IGNORECASE):
                spans.append(
                    TextSpan(
                        text=content[m.start():m.end()],
                        start_char=m.start(),
                        end_char=m.end(),
                    )
                )
                if len(spans) >= max_matches:
                    break

        return spans

    def suggest_annotations(
        self,
        document_id: str,
        auto_accept: bool = False
    ) -> SchemaBasedSuggestionResponse:
        """
        Suggest annotations for a document based on its schema fields.
        
        Uses OpenAI structured output to extract data according to the schema,
        then deterministically resolves text spans in backend code.
        
        Args:
            document_id: Document to suggest annotations for
            auto_accept: If True, automatically create the annotations
            
        Returns:
            SchemaBasedSuggestionResponse with suggestions
        """
        # Get document
        document = self.document_repo.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Get classification
        classification = self.repository.get_classification(document_id)
        if not classification:
            raise ValueError(f"Document {document_id} is not classified")
        
        # Get document type with schema
        doc_type = self.repository.get_document_type(classification.document_type_id)
        if not doc_type or not doc_type.schema_fields:
            raise ValueError(f"Document type has no schema fields")
        
        # Get labels for this document type only (no globals)
        labels = self.repository.list_labels(document_type_id=doc_type.id, include_global=False)
        label_map = {label.name: label for label in labels}
        
        content = document.content or ""
        if len(content) > 8000:
            content = content[:8000]  # Truncate for token limits
        
        # Build prompt for extraction only. Spans are computed in code.
        system_prompt = f"""You are an expert at analyzing {doc_type.name} documents and identifying where specific information appears.

Your task is to extract structured data according to the schema.
Return only structured field values. Do not include character offsets."""

        # Build field descriptions
        field_descriptions = []
        for field in doc_type.schema_fields:
            label_name = f"{field.name}"
            if field.type == "array" and field.items and field.items.type == "object":
                # For array of objects, describe nested structure
                props = field.items.properties or {}
                prop_names = ", ".join([f"{field.name}_{prop}" for prop in props.keys()])
                field_descriptions.append(
                    f"- {field.name}: {field.description or 'Array of objects'} "
                    f"(labels: {prop_names})"
                )
            else:
                field_descriptions.append(
                    f"- {field.name}: {field.description or 'No description'} "
                    f"(label: {label_name})"
                )
        
        user_prompt = f"""Document to analyze:

```
{content}
```

Schema fields to extract:
{chr(10).join(field_descriptions)}
"""

        print(f"\n{'='*60}")
        print("SCHEMA-BASED ANNOTATION SUGGESTION")
        print(f"{'='*60}")
        print(f"Document: {document.filename}")
        print(f"Type: {doc_type.name}")
        print(f"Fields: {[f.name for f in doc_type.schema_fields]}")
        print(f"{'='*60}\n")

        # Create dynamic Pydantic model for suggestions
        # This includes both the extracted values AND the text spans
        ExtractionModel = generate_pydantic_schema(
            doc_type.schema_fields,
            model_name=f"{doc_type.name.replace(' ', '')}Extraction"
        )
        model_name = getattr(self, "model", "gpt-5-mini")
        
        try:
            # First: Get structured extraction
            extraction_response = self.client.beta.chat.completions.parse(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=ExtractionModel,
                **reasoning_options_for_model(model_name),
            )
            
            extracted_data = extraction_response.choices[0].message.parsed
            extraction_dict = extracted_data.model_dump()
            
            print(f"Extracted: {extraction_dict}")
            
            # Build suggestions
            suggestions = []
            
            for field in doc_type.schema_fields:
                field_value = extraction_dict.get(field.name)
                if field_value is None:
                    continue
                
                # Determine label name
                if field.type == "array" and field.items and field.items.type == "object":
                    # For array of objects, use single label with key-value metadata
                    label_name = field.name
                    if label_name in label_map:
                        props = field.items.properties or {}
                        # Create one suggestion per value with key metadata
                        for item in (field_value if isinstance(field_value, list) else []):
                            for prop_name, prop_value in (item.items() if isinstance(item, dict) else []):
                                if prop_value and prop_name in props:
                                    matching_spans = self._find_text_spans(content, prop_value, max_matches=2)
                                    for span in matching_spans:
                                        suggestions.append(FieldAnnotationSuggestion(
                                            field_name=field.name,
                                            label_name=label_name,
                                            spans=[span],
                                            confidence=0.85,
                                            reasoning=f"Found {prop_name} value",
                                            metadata={"key": prop_name, "value": str(prop_value)}
                                        ))
                else:
                    # Simple field
                    label_name = field.name
                    if label_name in label_map:
                        matching_spans = self._find_text_spans(content, field_value, max_matches=2)
                        if matching_spans:
                            suggestions.append(FieldAnnotationSuggestion(
                                field_name=field.name,
                                label_name=label_name,
                                spans=matching_spans,
                                confidence=0.9,
                                reasoning=f"Extracted value: {field_value}"
                            ))
            
            # Auto-accept if requested
            if auto_accept:
                for suggestion in suggestions:
                    label = label_map.get(suggestion.label_name)
                    if label:
                        for span in suggestion.spans:
                            annotation_create = AnnotationCreate(
                                label_id=label.id,
                                annotation_type=AnnotationType.TEXT_SPAN,
                                text=span.text,
                                start_offset=span.start_char,
                                end_offset=span.end_char,
                                metadata=suggestion.metadata,
                                created_by="ai_schema_suggestion",
                            )
                            self.repository.create_annotation(document_id, annotation_create)
                print(f"Auto-accepted {len(suggestions)} annotation suggestions")
            
            return SchemaBasedSuggestionResponse(
                document_id=document_id,
                document_type_id=doc_type.id,
                suggestions=suggestions,
                extraction_preview=extraction_dict
            )
            
        except Exception as e:
            print(f"Schema-based suggestion error: {e}")
            import traceback
            traceback.print_exc()
            raise ValueError(f"Suggestion failed: {str(e)}")


_service: Optional[SchemaBasedSuggestionService] = None


def get_schema_based_suggestion_service() -> SchemaBasedSuggestionService:
    """Get or create the schema-based suggestion service singleton."""
    global _service
    if _service is None:
        _service = SchemaBasedSuggestionService()
    return _service
