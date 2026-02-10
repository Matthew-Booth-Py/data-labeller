"""Models for label suggestions based on document analysis."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class LabelSuggestion(BaseModel):
    """A suggested label based on document analysis."""

    id: str = Field(..., description="Unique identifier for this suggestion")
    name: str = Field(..., description="Suggested label name")
    description: str = Field(..., description="Suggested description for the label")
    reasoning: str = Field(..., description="Why this label was suggested")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    source_examples: list[str] = Field(
        default_factory=list,
        description="Example text from documents that match this label"
    )
    suggested_color: str = Field("#3b82f6", description="Suggested hex color")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class LabelSuggestionRequest(BaseModel):
    """Request for generating label suggestions."""

    sample_size: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of documents to sample for analysis"
    )
    existing_labels: bool = Field(
        default=True,
        description="Whether to consider existing labels when suggesting"
    )
    document_ids: list[str] | None = Field(
        default=None,
        description="Optional list of document IDs to analyze (filters to specific project)"
    )


class LabelSuggestionResponse(BaseModel):
    """Response containing label suggestions."""

    suggestions: list[LabelSuggestion] = Field(
        default_factory=list,
        description="List of suggested labels"
    )
    documents_analyzed: int = Field(..., description="Number of documents analyzed")
    model: str = Field(..., description="Model used for analysis")


class AcceptSuggestionRequest(BaseModel):
    """Request to accept a label suggestion."""

    color: Optional[str] = Field(
        None,
        pattern=r"^#[0-9a-fA-F]{6}$",
        description="Override the suggested color"
    )
    name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=50,
        description="Override the suggested name"
    )
    description: Optional[str] = Field(
        None,
        description="Override the suggested description"
    )


class AcceptSuggestionBody(BaseModel):
    """Combined body for accepting a suggestion with optional overrides."""
    
    # Suggestion fields
    id: str
    name: str
    description: str
    reasoning: str = ""
    confidence: float = 0.7
    source_examples: list[str] = Field(default_factory=list)
    suggested_color: str = "#3b82f6"
    
    # Override fields (optional)
    override_color: Optional[str] = Field(None, pattern=r"^#[0-9a-fA-F]{6}$")
    override_name: Optional[str] = None
    override_description: Optional[str] = None
