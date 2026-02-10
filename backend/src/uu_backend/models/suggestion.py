"""Models for LLM-assisted label suggestions."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SuggestedAnnotation(BaseModel):
    """A suggested annotation from the LLM."""
    
    label_id: str = Field(..., description="ID of the label to apply")
    label_name: str = Field(..., description="Name of the label")
    text: str = Field(..., description="The text span to annotate")
    start_offset: int = Field(..., description="Start character offset")
    end_offset: int = Field(..., description="End character offset")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score 0-1")
    reasoning: Optional[str] = Field(None, description="Why this annotation was suggested")
    metadata: Optional[dict] = Field(None, description="Structured metadata (e.g., key-value pairs)")


class SuggestionRequest(BaseModel):
    """Request for annotation suggestions."""
    
    label_ids: Optional[list[str]] = Field(
        None, 
        description="Specific label IDs to suggest for (None = all labels)"
    )
    max_suggestions: int = Field(
        20, 
        ge=1, 
        le=100, 
        description="Maximum number of suggestions to return"
    )
    min_confidence: float = Field(
        0.5, 
        ge=0.0, 
        le=1.0, 
        description="Minimum confidence threshold"
    )


class SuggestionResponse(BaseModel):
    """Response containing suggested annotations."""
    
    document_id: str
    suggestions: list[SuggestedAnnotation]
    examples_used: int = Field(..., description="Number of few-shot examples used")
    model: str = Field(..., description="Model used for suggestions")
    generated_at: datetime = Field(default_factory=datetime.utcnow)
