"""Models for feedback and ML training."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class FeedbackType(str, Enum):
    """Types of feedback signals."""
    
    CORRECT = "correct"  # User confirmed suggestion was correct
    INCORRECT = "incorrect"  # User marked suggestion as wrong
    ACCEPTED = "accepted"  # User accepted and created annotation
    REJECTED = "rejected"  # User rejected suggestion


class FeedbackSource(str, Enum):
    """Source of the training example."""
    
    SUGGESTION = "suggestion"  # From LLM/ML suggestion
    MANUAL = "manual"  # User created annotation manually


class Feedback(BaseModel):
    """A feedback record for training the ML model."""
    
    id: str = Field(..., description="Unique identifier")
    document_id: str = Field(..., description="Document ID")
    label_id: str = Field(..., description="Label ID")
    label_name: Optional[str] = Field(None, description="Label name for convenience")
    text: str = Field(..., description="The text span")
    start_offset: int = Field(..., description="Start character offset")
    end_offset: int = Field(..., description="End character offset")
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    source: FeedbackSource = Field(..., description="Where this example came from")
    embedding: Optional[list[float]] = Field(None, description="Text embedding vector")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FeedbackCreate(BaseModel):
    """Request to submit feedback."""
    
    document_id: str = Field(..., description="Document ID")
    label_id: str = Field(..., description="Label ID")
    text: str = Field(..., description="The text span")
    start_offset: int = Field(..., description="Start character offset")
    end_offset: int = Field(..., description="End character offset")
    feedback_type: FeedbackType = Field(..., description="Type of feedback")
    source: FeedbackSource = Field(
        FeedbackSource.SUGGESTION, 
        description="Where this example came from"
    )


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""
    
    feedback: Feedback
    should_retrain: bool = Field(..., description="Whether model should be retrained")
    feedback_count: int = Field(..., description="Total feedback count")


class TrainingStatus(BaseModel):
    """Status of the ML model training."""
    
    is_trained: bool = Field(..., description="Whether a model exists")
    sample_count: int = Field(..., description="Number of training samples")
    positive_samples: int = Field(..., description="Correct/accepted samples")
    negative_samples: int = Field(..., description="Incorrect/rejected samples")
    labels_count: int = Field(..., description="Number of unique labels")
    last_trained_at: Optional[datetime] = Field(None, description="When model was last trained")
    accuracy: Optional[float] = Field(None, description="Validation accuracy")
    model_path: Optional[str] = Field(None, description="Path to saved model")
    min_samples_required: int = Field(20, description="Minimum samples to train")
    ready_to_train: bool = Field(..., description="Whether enough samples exist")


class TrainingResult(BaseModel):
    """Result of a training run."""
    
    success: bool
    message: str
    accuracy: Optional[float] = None
    sample_count: int = 0
    trained_at: Optional[datetime] = None
