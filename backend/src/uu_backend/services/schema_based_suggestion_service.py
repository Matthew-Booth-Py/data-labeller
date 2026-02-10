"""Schema-based annotation suggestion service using structured output."""

from typing import Optional
from openai import OpenAI
from pydantic import BaseModel, Field

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.annotation import Annotation
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
        self.client = OpenAI()
        self.sqlite_client = get_sqlite_client()
        self.vector_store = get_vector_store()

    def suggest_annotations(
        self,
        document_id: str,
        auto_accept: bool = False
    ) -> SchemaBasedSuggestionResponse:
        """
        Suggest annotations for a document based on its schema fields.
        
        Uses OpenAI structured output to:
        1. Extract data according to the schema
        2. Identify the text spans where each value was found
        3. Create annotation suggestions with exact character positions
        
        Args:
            document_id: Document to suggest annotations for
            auto_accept: If True, automatically create the annotations
            
        Returns:
            SchemaBasedSuggestionResponse with suggestions
        """
        # Get document
        document = self.vector_store.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Get classification
        classification = self.sqlite_client.get_classification(document_id)
        if not classification:
            raise ValueError(f"Document {document_id} is not classified")
        
        # Get document type with schema
        doc_type = self.sqlite_client.get_document_type(classification.document_type_id)
        if not doc_type or not doc_type.schema_fields:
            raise ValueError(f"Document type has no schema fields")
        
        # Get labels for this document type
        labels = self.sqlite_client.list_labels(document_type_id=doc_type.id)
        label_map = {label.name: label for label in labels}
        
        content = document.content or ""
        if len(content) > 8000:
            content = content[:8000]  # Truncate for token limits
        
        # Build prompt for annotation suggestion
        system_prompt = f"""You are an expert at analyzing {doc_type.name} documents and identifying where specific information appears.

Your task is to:
1. Extract structured data according to the schema
2. For each extracted value, identify the EXACT text span(s) in the document where you found it
3. Provide character positions (start_char, end_char) for each span

Be precise with character positions. Count from the beginning of the document (position 0)."""

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

For each field value you extract, identify the exact text span(s) where you found it in the document above.
Provide the character start and end positions for each span."""

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
        
        try:
            # First: Get structured extraction
            extraction_response = self.client.beta.chat.completions.parse(
                model="gpt-4o-2024-08-06",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format=ExtractionModel,
            )
            
            extracted_data = extraction_response.choices[0].message.parsed
            extraction_dict = extracted_data.model_dump()
            
            print(f"Extracted: {extraction_dict}")
            
            # Second: Get text span suggestions
            # We need another call to identify WHERE each value was found
            span_prompt = f"""Based on the extraction you just performed, identify the exact character positions where you found each value.

Document (with character positions):
```
{content}
```

Extracted values:
{extraction_dict}

For each extracted value, provide:
1. The field name
2. The exact text from the document
3. Start character position (0-indexed)
4. End character position

Return as JSON array of objects with: field_name, text, start_char, end_char"""

            span_response = self.client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are an expert at identifying text positions in documents."},
                    {"role": "user", "content": span_prompt}
                ],
                response_format={"type": "json_object"}
            )
            
            spans_data = span_response.choices[0].message.content
            import json
            spans = json.loads(spans_data)
            
            print(f"Spans: {spans}")
            
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
                                    # Find matching spans for this specific value
                                    matching_spans = [
                                        s for s in spans.get("spans", [])
                                        if s.get("field_name") == f"{field.name}.{prop_name}"
                                        or str(prop_value) in s.get("text", "")
                                    ]
                                    
                                    for span in matching_spans:
                                        suggestions.append(FieldAnnotationSuggestion(
                                            field_name=field.name,
                                            label_name=label_name,
                                            spans=[TextSpan(
                                                text=span["text"],
                                                start_char=span["start_char"],
                                                end_char=span["end_char"]
                                            )],
                                            confidence=0.85,
                                            reasoning=f"Found {prop_name} value",
                                            metadata={"key": prop_name, "value": str(prop_value)}
                                        ))
                else:
                    # Simple field
                    label_name = field.name
                    if label_name in label_map:
                        # Find spans for this field
                        matching_spans = [
                            s for s in spans.get("spans", [])
                            if s.get("field_name") == field.name
                            or str(field_value) in s.get("text", "")
                        ]
                        
                        if matching_spans:
                            suggestions.append(FieldAnnotationSuggestion(
                                field_name=field.name,
                                label_name=label_name,
                                spans=[
                                    TextSpan(
                                        text=s["text"],
                                        start_char=s["start_char"],
                                        end_char=s["end_char"]
                                    )
                                    for s in matching_spans
                                ],
                                confidence=0.9,
                                reasoning=f"Extracted value: {field_value}"
                            ))
            
            # Auto-accept if requested
            if auto_accept:
                for suggestion in suggestions:
                    label = label_map.get(suggestion.label_name)
                    if label:
                        for span in suggestion.spans:
                            annotation = Annotation(
                                id=None,  # Will be generated
                                document_id=document_id,
                                label_id=label.id,
                                text=span.text,
                                start_char=span.start_char,
                                end_char=span.end_char,
                                page_number=None,
                                confidence=suggestion.confidence,
                                source="ai_schema_suggestion",
                                created_at=None,  # Will be set by DB
                                updated_at=None
                            )
                            self.sqlite_client.create_annotation(annotation)
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
