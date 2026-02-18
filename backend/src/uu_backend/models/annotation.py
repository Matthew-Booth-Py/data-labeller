"""Ground truth annotation models for data labelling."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class AnnotationType(str, Enum):
    """Types of annotations for different document formats."""
    
    TEXT_SPAN = "text_span"  # Character offsets for text documents
    BBOX = "bbox"  # Bounding box for PDFs and images
    TABLE_ROW = "table_row"  # Multi-field row for array fields


class TextSpanData(BaseModel):
    """Text span annotation data for text documents."""
    
    start: int = Field(..., description="Start character offset")
    end: int = Field(..., description="End character offset")
    text: str = Field(..., description="Selected text content")


class BoundingBoxData(BaseModel):
    """Bounding box annotation data for PDFs and images."""
    
    page: int = Field(..., description="Page number (1-indexed)")
    x: float = Field(..., description="X coordinate (top-left)")
    y: float = Field(..., description="Y coordinate (top-left)")
    width: float = Field(..., description="Box width")
    height: float = Field(..., description="Box height")
    text: Optional[str] = Field(None, description="Text content in bbox (if available)")


class TableRowFieldData(BaseModel):
    """Field data within a table row."""
    
    name: str = Field(..., description="Field name")
    bbox: Optional[BoundingBoxData] = Field(None, description="Bounding box for this field")
    text_span: Optional[TextSpanData] = Field(None, description="Text span for this field")


class TableRowData(BaseModel):
    """Table row annotation data for array fields."""
    
    row_index: int = Field(..., description="Row index in the array")
    fields: list[TableRowFieldData] = Field(..., description="Fields within this row")


class GroundTruthAnnotationCreate(BaseModel):
    """Request model for creating a ground truth annotation."""
    
    document_id: str = Field(..., description="Document ID")
    field_name: str = Field(..., description="Schema field name")
    value: Any = Field(..., description="Ground truth value")
    annotation_type: AnnotationType = Field(..., description="Type of annotation")
    annotation_data: dict[str, Any] = Field(..., description="Location/coordinate data")
    confidence: float = Field(1.0, ge=0.0, le=1.0, description="Confidence score")
    labeled_by: str = Field("manual", description="Source: manual, ai-suggested, ai-approved")


class GroundTruthAnnotation(BaseModel):
    """A ground truth annotation for a document field."""
    
    id: str = Field(..., description="Unique annotation ID")
    document_id: str = Field(..., description="Document ID")
    field_name: str = Field(..., description="Schema field name")
    value: Any = Field(..., description="Ground truth value")
    annotation_type: AnnotationType = Field(..., description="Type of annotation")
    annotation_data: dict[str, Any] = Field(..., description="Location/coordinate data")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    labeled_by: str = Field(..., description="Source: manual, ai-suggested, ai-approved")
    is_approved: bool = Field(False, description="Whether AI suggestion was approved")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")


class GroundTruthAnnotationUpdate(BaseModel):
    """Request model for updating a ground truth annotation."""
    
    value: Optional[Any] = Field(None, description="Updated value")
    annotation_data: Optional[dict[str, Any]] = Field(None, description="Updated location data")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    labeled_by: Optional[str] = None


class AnnotationSuggestion(BaseModel):
    """AI-suggested annotation (not yet saved as ground truth)."""
    
    id: str = Field(..., description="Temporary suggestion ID")
    document_id: str = Field(..., description="Document ID")
    field_name: str = Field(..., description="Schema field name")
    value: Any = Field(..., description="Suggested value")
    annotation_type: AnnotationType = Field(..., description="Type of annotation")
    annotation_data: dict[str, Any] = Field(..., description="Location/coordinate data")
    confidence: float = Field(..., ge=0.0, le=1.0, description="AI confidence score")
    text_snippet: Optional[str] = Field(None, description="Text snippet from document")


class AnnotationSuggestionResponse(BaseModel):
    """Response model for AI annotation suggestions."""
    
    suggestions: list[AnnotationSuggestion]
    total: int


class GroundTruthAnnotationListResponse(BaseModel):
    """Response model for listing ground truth annotations."""
    
    annotations: list[GroundTruthAnnotation]
    total: int


class GroundTruthAnnotationResponse(BaseModel):
    """Response model for a single ground truth annotation."""
    
    annotation: GroundTruthAnnotation


class ApproveAnnotationRequest(BaseModel):
    """Request model for approving an AI suggestion."""
    
    annotation_id: str = Field(..., description="Suggestion ID to approve")
    edited_value: Optional[Any] = Field(None, description="Edited value (if user modified)")
