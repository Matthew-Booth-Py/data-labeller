"""Taxonomy and document classification models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class FieldType(str, Enum):
    """Supported field types for schema definitions."""

    STRING = "string"
    NUMBER = "number"
    DATE = "date"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"


class SchemaField(BaseModel):
    """A field definition within a document type schema."""

    name: str = Field(..., description="Field name/key")
    type: FieldType = Field(..., description="Field data type")
    description: Optional[str] = Field(None, description="Field description")
    required: bool = Field(False, description="Whether field is required")
    extraction_prompt: Optional[str] = Field(
        None, description="LLM prompt for extracting this field"
    )
    properties: Optional[dict[str, "SchemaField"]] = Field(
        None, description="Nested properties for object types"
    )
    items: Optional["SchemaField"] = Field(
        None, description="Item schema for array types"
    )


class DocumentTypeCreate(BaseModel):
    """Request model for creating a document type."""

    name: str = Field(..., description="Document type name", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="Document type description")
    schema_fields: list[SchemaField] = Field(
        default_factory=list, description="Schema field definitions"
    )
    system_prompt: Optional[str] = Field(
        None, description="System prompt for LLM extraction"
    )
    post_processing: Optional[str] = Field(
        None, description="Post-processing code (Python/JS)"
    )


class DocumentTypeUpdate(BaseModel):
    """Request model for updating a document type."""

    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    schema_fields: Optional[list[SchemaField]] = None
    system_prompt: Optional[str] = None
    post_processing: Optional[str] = None


class DocumentType(BaseModel):
    """A document type definition with extraction schema."""

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Document type name")
    description: Optional[str] = Field(None, description="Document type description")
    schema_fields: list[SchemaField] = Field(
        default_factory=list, description="Schema field definitions"
    )
    system_prompt: Optional[str] = Field(
        None, description="System prompt for LLM extraction"
    )
    post_processing: Optional[str] = Field(
        None, description="Post-processing code (Python/JS)"
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
    confidence: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Classification confidence score"
    )
    labeled_by: Optional[str] = Field(None, description="User who labeled this")


class Classification(BaseModel):
    """A document's classification assignment."""

    document_id: str = Field(..., description="Document ID")
    document_type_id: str = Field(..., description="Assigned document type ID")
    document_type_name: Optional[str] = Field(None, description="Document type name")
    confidence: Optional[float] = Field(None, description="Classification confidence")
    labeled_by: Optional[str] = Field(None, description="User who labeled this")
    created_at: datetime = Field(..., description="Classification timestamp")


class ClassificationResponse(BaseModel):
    """Response model for document classification."""

    classification: Classification


class ExtractedField(BaseModel):
    """An extracted field value from a document."""

    field_name: str = Field(..., description="Field name from schema")
    value: Any = Field(..., description="Extracted value")
    confidence: Optional[float] = Field(None, description="Extraction confidence")
    source_text: Optional[str] = Field(None, description="Source text for extraction")


class ExtractionResult(BaseModel):
    """Extraction results for a document."""

    document_id: str
    document_type_id: str
    fields: list[ExtractedField]
    extracted_at: datetime
