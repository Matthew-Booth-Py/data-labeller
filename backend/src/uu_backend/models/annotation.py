"""Annotation models for document labeling."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AnnotationType(str, Enum):
    """Types of annotations supported."""

    TEXT_SPAN = "text_span"  # Highlight text region with label
    BOUNDING_BOX = "bounding_box"  # Rectangle on PDF/image
    KEY_VALUE = "key_value"  # Key-value pair extraction
    ENTITY = "entity"  # Named entity recognition
    CLASSIFICATION = "classification"  # Document-level label


class Label(BaseModel):
    """A label/tag definition for annotations."""

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Label name (e.g., 'Person', 'Date', 'Amount')")
    color: str = Field("#3b82f6", description="Hex color for display")
    description: Optional[str] = Field(None, description="Label description")
    shortcut: Optional[str] = Field(None, description="Keyboard shortcut (e.g., '1', 'p')")
    entity_type: Optional[str] = Field(None, description="Entity type for NER (Person, Org, etc.)")
    document_type_id: Optional[str] = Field(None, description="Document type this label belongs to (null = global)")


class LabelCreate(BaseModel):
    """Request model for creating a label."""

    name: str = Field(..., min_length=1, max_length=50)
    color: str = Field("#3b82f6", pattern=r"^#[0-9a-fA-F]{6}$")
    description: Optional[str] = None
    shortcut: Optional[str] = Field(None, max_length=1)
    entity_type: Optional[str] = None
    document_type_id: Optional[str] = Field(None, description="Document type this label belongs to")


class LabelUpdate(BaseModel):
    """Request model for updating a label."""

    name: Optional[str] = Field(None, min_length=1, max_length=50)
    color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    description: Optional[str] = None
    shortcut: Optional[str] = None
    entity_type: Optional[str] = None
    document_type_id: Optional[str] = None


class LabelListResponse(BaseModel):
    """Response model for listing labels."""

    labels: list[Label]
    total: int


class AnnotationBase(BaseModel):
    """Base fields for all annotation types."""

    document_id: str = Field(..., description="Document being annotated")
    label_id: str = Field(..., description="Label/tag applied")
    annotation_type: AnnotationType = Field(..., description="Type of annotation")
    created_by: Optional[str] = Field(None, description="User who created this")


class TextSpanAnnotation(AnnotationBase):
    """Text span annotation - highlights a region of text."""

    annotation_type: AnnotationType = AnnotationType.TEXT_SPAN
    start_offset: int = Field(..., ge=0, description="Start character offset")
    end_offset: int = Field(..., gt=0, description="End character offset")
    text: str = Field(..., description="Selected text content")


class BoundingBoxAnnotation(AnnotationBase):
    """Bounding box annotation - rectangle on PDF/image."""

    annotation_type: AnnotationType = AnnotationType.BOUNDING_BOX
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    x: float = Field(..., ge=0, description="X coordinate (percentage 0-100)")
    y: float = Field(..., ge=0, description="Y coordinate (percentage 0-100)")
    width: float = Field(..., gt=0, description="Width (percentage)")
    height: float = Field(..., gt=0, description="Height (percentage)")
    text: Optional[str] = Field(None, description="OCR text in region")


class KeyValueAnnotation(AnnotationBase):
    """Key-value pair annotation."""

    annotation_type: AnnotationType = AnnotationType.KEY_VALUE
    key_text: str = Field(..., description="Key/field name text")
    key_start: int = Field(..., ge=0, description="Key start offset")
    key_end: int = Field(..., gt=0, description="Key end offset")
    value_text: str = Field(..., description="Value text")
    value_start: int = Field(..., ge=0, description="Value start offset")
    value_end: int = Field(..., gt=0, description="Value end offset")


class EntityAnnotation(AnnotationBase):
    """Named entity annotation."""

    annotation_type: AnnotationType = AnnotationType.ENTITY
    start_offset: int = Field(..., ge=0, description="Start character offset")
    end_offset: int = Field(..., gt=0, description="End character offset")
    text: str = Field(..., description="Entity text")
    entity_type: str = Field(..., description="Entity type (Person, Org, Location, etc.)")
    normalized_value: Optional[str] = Field(None, description="Normalized/canonical value")


class Annotation(BaseModel):
    """Full annotation model with all fields."""

    id: str = Field(..., description="Unique identifier")
    document_id: str = Field(..., description="Document ID")
    label_id: str = Field(..., description="Label ID")
    label_name: Optional[str] = Field(None, description="Label name (joined)")
    label_color: Optional[str] = Field(None, description="Label color (joined)")
    annotation_type: AnnotationType = Field(..., description="Type of annotation")

    # Text span fields
    start_offset: Optional[int] = Field(None, description="Start offset for text spans")
    end_offset: Optional[int] = Field(None, description="End offset for text spans")
    text: Optional[str] = Field(None, description="Selected text")

    # Bounding box fields
    page: Optional[int] = Field(None, description="Page number")
    x: Optional[float] = Field(None, description="X coordinate")
    y: Optional[float] = Field(None, description="Y coordinate")
    width: Optional[float] = Field(None, description="Width")
    height: Optional[float] = Field(None, description="Height")

    # Key-value fields
    key_text: Optional[str] = Field(None, description="Key text")
    key_start: Optional[int] = Field(None, description="Key start offset")
    key_end: Optional[int] = Field(None, description="Key end offset")
    value_text: Optional[str] = Field(None, description="Value text")
    value_start: Optional[int] = Field(None, description="Value start offset")
    value_end: Optional[int] = Field(None, description="Value end offset")

    # Entity fields
    entity_type: Optional[str] = Field(None, description="Entity type")
    normalized_value: Optional[str] = Field(None, description="Normalized value")

    # Table/Array grouping
    row_index: Optional[int] = Field(None, description="Row index for table data (0-based)")
    group_id: Optional[str] = Field(None, description="Group ID to link related annotations (e.g., same table row)")

    # Structured metadata (for key-value pairs, custom fields, etc.)
    metadata: Optional[dict[str, Any]] = Field(None, description="Structured metadata (e.g., {'key': 'claim_item', 'value': 'Labor'})")

    # Metadata
    created_by: Optional[str] = Field(None, description="Creator")
    created_at: datetime = Field(..., description="Creation timestamp")


class AnnotationCreate(BaseModel):
    """Request model for creating an annotation."""

    label_id: str = Field(..., description="Label ID to apply")
    annotation_type: AnnotationType = Field(..., description="Type of annotation")

    # Text span / Entity fields
    start_offset: Optional[int] = Field(None, ge=0)
    end_offset: Optional[int] = Field(None, gt=0)
    text: Optional[str] = None

    # Bounding box fields
    page: Optional[int] = Field(None, ge=1)
    x: Optional[float] = Field(None, ge=0)
    y: Optional[float] = Field(None, ge=0)
    width: Optional[float] = Field(None, gt=0)
    height: Optional[float] = Field(None, gt=0)

    # Key-value fields
    key_text: Optional[str] = None
    key_start: Optional[int] = Field(None, ge=0)
    key_end: Optional[int] = Field(None, gt=0)
    value_text: Optional[str] = None
    value_start: Optional[int] = Field(None, ge=0)
    value_end: Optional[int] = Field(None, gt=0)

    # Entity fields
    entity_type: Optional[str] = None
    normalized_value: Optional[str] = None

    # Table/Array grouping
    row_index: Optional[int] = Field(None, description="Row index for table data (0-based)")
    group_id: Optional[str] = Field(None, description="Group ID to link related annotations")

    # Structured metadata
    metadata: Optional[dict[str, Any]] = Field(None, description="Structured metadata (e.g., {'key': 'claim_item', 'value': 'Labor'})")

    created_by: Optional[str] = None


class AnnotationUpdate(BaseModel):
    """Request model for updating an annotation."""

    label_id: Optional[str] = None
    text: Optional[str] = None
    entity_type: Optional[str] = None
    normalized_value: Optional[str] = None


class AnnotationListResponse(BaseModel):
    """Response model for listing annotations."""

    annotations: list[Annotation]
    total: int


class AnnotationResponse(BaseModel):
    """Response model for a single annotation."""

    annotation: Annotation


class AnnotationStats(BaseModel):
    """Statistics about annotations for a document."""

    document_id: str
    total_annotations: int
    by_type: dict[str, int]
    by_label: dict[str, int]
