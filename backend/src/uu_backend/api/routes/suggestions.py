"""API routes for annotation suggestions and ML feedback."""

from fastapi import APIRouter, HTTPException, Query

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.feedback import (
    Feedback,
    FeedbackCreate,
    FeedbackResponse,
    TrainingResult,
    TrainingStatus,
)
from uu_backend.models.suggestion import SuggestionRequest, SuggestionResponse
from uu_backend.services.ml_service import get_ml_service
from uu_backend.services.suggestion_service import get_suggestion_service

router = APIRouter()


# ============================================================================
# Suggestion Endpoints
# ============================================================================


@router.post("/documents/{document_id}/suggest", response_model=SuggestionResponse)
async def suggest_annotations(
    document_id: str,
    request: SuggestionRequest = None,
    force_llm: bool = Query(False, description="Force LLM even if local model available"),
):
    """
    Generate annotation suggestions for a document.

    Uses hybrid approach:
    - Local ML model when trained (fast, free)
    - LLM fallback when not enough training data
    """
    if request is None:
        request = SuggestionRequest()

    # Get document content
    vector_store = get_vector_store()
    document = vector_store.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail=f"Document not found: {document_id}")

    if not document.content:
        raise HTTPException(status_code=400, detail="Document has no content to analyze")

    try:
        service = get_suggestion_service()
        suggestions = service.generate_suggestions(
            document_id=document_id,
            document_content=document.content,
            label_ids=request.label_ids,
            max_suggestions=request.max_suggestions,
            min_confidence=request.min_confidence,
            force_llm=force_llm,
        )
        return suggestions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate suggestions: {e}")


# ============================================================================
# Feedback Endpoints
# ============================================================================


@router.post("/feedback", response_model=FeedbackResponse, status_code=201)
async def submit_feedback(data: FeedbackCreate):
    """
    Submit feedback for a suggestion or annotation.

    This data is used to train the local ML model.
    Feedback types:
    - correct: Suggestion was correct
    - incorrect: Suggestion was wrong
    - accepted: User accepted and created annotation
    - rejected: User rejected suggestion
    """
    sqlite = get_sqlite_client()
    ml_service = get_ml_service()

    try:
        # Generate embedding for the text
        embedding = ml_service.embed_text(data.text)

        # Create feedback record
        feedback = sqlite.create_feedback(data, embedding=embedding)

        # Check if we should retrain
        feedback_count = sqlite.get_feedback_count()
        should_retrain = ml_service.should_retrain()

        return FeedbackResponse(
            feedback=feedback,
            should_retrain=should_retrain,
            feedback_count=feedback_count,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {e}")


@router.get("/feedback", response_model=list[Feedback])
async def list_feedback(
    label_id: str = Query(None, description="Filter by label ID"),
    limit: int = Query(100, ge=1, le=1000),
):
    """List feedback records."""
    sqlite = get_sqlite_client()
    feedback = sqlite.list_feedback(label_id=label_id)
    return feedback[:limit]


# ============================================================================
# Model Status Endpoints
# ============================================================================


@router.get("/model/status", response_model=TrainingStatus)
async def get_model_status():
    """
    Get ML model training status.

    Returns information about:
    - Whether model is trained
    - Number of training samples
    - Accuracy if trained
    - Whether ready to train
    """
    ml_service = get_ml_service()
    return ml_service.get_training_status()


@router.post("/model/train", response_model=TrainingResult)
async def train_model():
    """
    Manually trigger model training.

    The model will train on all positive feedback (correct/accepted).
    Requires at least 20 positive samples and 2 different labels.
    """
    ml_service = get_ml_service()
    status = ml_service.get_training_status()

    if not status.ready_to_train:
        return TrainingResult(
            success=False,
            message=f"Not ready to train. Need {status.min_samples_required} positive samples "
            f"(have {status.positive_samples}) and at least 2 labels (have {status.labels_count})",
            sample_count=status.sample_count,
        )

    return ml_service.train_model()
