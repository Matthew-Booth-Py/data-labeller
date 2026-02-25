"""Taxonomy and document classification models."""

from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from pydantic import BaseModel, Field


class FieldType(StrEnum):
    """Supported field types for schema definitions."""

    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class VisualContentType(StrEnum):
    """Detected content type from visual analysis."""

    TABLE = "table"
    FORM = "form"
    LIST = "list"
    PARAGRAPH = "paragraph"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class SchemaField(BaseModel):
    """A field definition within a document type schema."""

    name: str = Field(..., description="Field name/key")
    type: FieldType = Field(..., description="Field data type")
    description: str | None = Field(None, description="Field description")
    required: bool = Field(False, description="Whether field is required")
    extraction_prompt: str | None = Field(None, description="LLM prompt for extracting this field")
    order: int | None = Field(
        None, description="Display order for nested properties (lower = first)"
    )
    properties: dict[str, "SchemaField"] | None = Field(
        None, description="Nested properties for object types"
    )
    items: Optional["SchemaField"] = Field(None, description="Item schema for array types")
    template_field_id: str | None = Field(
        None, description="Optional linked global field template ID"
    )
    # Visual analysis fields (auto-populated from reference image)
    visual_content_type: VisualContentType | None = Field(
        None, description="Detected content type from reference image analysis"
    )
    visual_guidance: str | None = Field(
        None, description="Auto-generated extraction guidance from visual analysis"
    )
    visual_features: list[str] | None = Field(
        None, description="Distinguishing visual features for retrieval"
    )
    reference_image_hash: str | None = Field(
        None, description="Hash of the reference image used for analysis"
    )


class DocumentTypeCreate(BaseModel):
    """Request model for creating a document type."""

    name: str = Field(..., description="Document type name", min_length=1, max_length=100)
    description: str | None = Field(None, description="Document type description")
    schema_fields: list[SchemaField] = Field(
        default_factory=list, description="Schema field definitions"
    )
    system_prompt: str | None = Field(None, description="System prompt for LLM extraction")
    post_processing: str | None = Field(None, description="Post-processing code (Python/JS)")
    extraction_model: str | None = Field(
        None, description="LLM model used for extraction for this document type"
    )
    ocr_engine: str | None = Field(None, description="OCR engine selection for this document type")


class DocumentTypeUpdate(BaseModel):
    """Request model for updating a document type."""

    name: str | None = Field(None, min_length=1, max_length=100)
    description: str | None = None
    schema_fields: list[SchemaField] | None = None
    system_prompt: str | None = None
    post_processing: str | None = None
    extraction_model: str | None = None
    ocr_engine: str | None = None


class DocumentType(BaseModel):
    """A document type definition with extraction schema."""

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Document type name")
    description: str | None = Field(None, description="Document type description")
    schema_fields: list[SchemaField] = Field(
        default_factory=list, description="Schema field definitions"
    )
    system_prompt: str | None = Field(None, description="System prompt for LLM extraction")
    post_processing: str | None = Field(None, description="Post-processing code (Python/JS)")
    extraction_model: str | None = Field(
        None, description="LLM model used for extraction for this document type"
    )
    ocr_engine: str | None = Field(None, description="OCR engine selection for this document type")
    schema_version_id: str | None = Field(
        None, description="Current schema/config version ID for this document type"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class DocumentTypeResponse(BaseModel):
    """Response model for a single document type."""

    type: DocumentType


class DocumentTypeListResponse(BaseModel):
    """Response model for listing document types."""

    types: list[DocumentType]
    total: int


class ClassificationCreate(BaseModel):
    """Request model for classifying a document."""

    document_type_id: str = Field(..., description="Document type ID to assign")
    confidence: float | None = Field(
        None, ge=0.0, le=1.0, description="Classification confidence score"
    )
    labeled_by: str | None = Field(None, description="User who labeled this")


class Classification(BaseModel):
    """A document's classification assignment."""

    document_id: str = Field(..., description="Document ID")
    document_type_id: str = Field(..., description="Assigned document type ID")
    document_type_name: str | None = Field(None, description="Document type name")
    confidence: float | None = Field(None, description="Classification confidence")
    labeled_by: str | None = Field(None, description="User who labeled this")
    created_at: datetime = Field(..., description="Classification timestamp")


class ClassificationResponse(BaseModel):
    """Response model for document classification."""

    classification: Classification


class ExtractedField(BaseModel):
    """An extracted field value from a document."""

    field_name: str = Field(..., description="Field name from schema")
    value: Any = Field(..., description="Extracted value")
    confidence: float | None = Field(None, description="Extraction confidence")
    source_text: str | None = Field(None, description="Source text for extraction")


class ExtractionResult(BaseModel):
    """Extraction results for a document."""

    document_id: str
    document_type_id: str
    fields: list[ExtractedField]
    schema_version_id: str | None = None
    prompt_version_id: str | None = None
    extracted_at: datetime
    # Pages that were actually used for extraction (populated by retrieval-vision path)
    source_page_numbers: list[int] = Field(default_factory=list)


class GlobalField(BaseModel):
    """Reusable field template available across document types."""

    id: str
    name: str = Field(..., min_length=1, max_length=100)
    type: FieldType
    prompt: str = Field(..., min_length=1)
    description: str | None = None
    extraction_model: str | None = None
    ocr_engine: str | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime


class GlobalFieldCreate(BaseModel):
    """Request model for creating a reusable global field."""

    name: str = Field(..., min_length=1, max_length=100)
    type: FieldType
    prompt: str = Field(..., min_length=1)
    description: str | None = None
    extraction_model: str | None = None
    ocr_engine: str | None = None
    created_by: str | None = None


class GlobalFieldUpdate(BaseModel):
    """Request model for updating a reusable global field."""

    name: str | None = Field(None, min_length=1, max_length=100)
    type: FieldType | None = None
    prompt: str | None = Field(None, min_length=1)
    description: str | None = None
    extraction_model: str | None = None
    ocr_engine: str | None = None


class FieldPropertySuggestion(BaseModel):
    """Suggested property for object/array-of-object field definitions. Supports nesting."""

    name: str = Field(..., min_length=1)
    type: FieldType
    description: str | None = None
    items_type: FieldType | None = Field(
        None, description="For array properties, the type of array items"
    )
    properties: list["FieldPropertySuggestion"] | None = Field(
        None, description="Nested properties for object or array-of-object sub-properties"
    )


class FieldAssistantRequest(BaseModel):
    """Request model for AI-assisted field creation."""

    user_input: str = Field(
        ..., min_length=3, description="Natural language description of desired field"
    )
    document_type_id: str | None = Field(None, description="Optional document type context")
    existing_field_names: list[str] = Field(
        default_factory=list,
        description="Existing field names to avoid collisions",
    )
    screenshot_base64: str | None = Field(
        None,
        description="Optional base64-encoded screenshot to help draft the schema",
    )


class FieldAssistantResponse(BaseModel):
    """Response model for AI-assisted field creation suggestions."""

    name: str
    type: FieldType
    description: str | None = None
    extraction_prompt: str
    items_type: FieldType | None = None
    object_properties: list[FieldPropertySuggestion] = Field(default_factory=list)


class GlobalFieldListResponse(BaseModel):
    """Response model for listing global fields."""

    fields: list[GlobalField]
    total: int
