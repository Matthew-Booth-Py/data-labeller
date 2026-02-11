"""DRF views for suggestions and ML feedback endpoints."""

from pydantic import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.feedback import (
    FeedbackCreate,
    FeedbackResponse,
    TrainingResult,
)
from uu_backend.models.suggestion import SuggestionRequest
from uu_backend.repositories import get_repository
from uu_backend.services.ml_service import get_ml_service
from uu_backend.services.suggestion_service import get_suggestion_service


def _validation_error_response(exc: ValidationError) -> Response:
    return Response({"detail": exc.errors()}, status=422)


class DocumentSuggestView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request, document_id: str):
        body = request.data if isinstance(request.data, dict) else {}
        try:
            parsed = SuggestionRequest.model_validate(body or {})
        except ValidationError as exc:
            return _validation_error_response(exc)

        force_llm = str(request.query_params.get("force_llm", "false")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        vector_store = get_vector_store()
        document = vector_store.get_document(document_id)
        if not document:
            return Response({"detail": f"Document not found: {document_id}"}, status=404)
        if not document.content:
            return Response({"detail": "Document has no content to analyze"}, status=400)

        try:
            service = get_suggestion_service()
            suggestions = service.generate_suggestions(
                document_id=document_id,
                document_content=document.content,
                label_ids=parsed.label_ids,
                max_suggestions=parsed.max_suggestions,
                min_confidence=parsed.min_confidence,
                force_llm=force_llm,
            )
            return Response(suggestions.model_dump(mode="json"))
        except Exception as exc:
            return Response({"detail": f"Failed to generate suggestions: {exc}"}, status=500)


class FeedbackView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        try:
            parsed = FeedbackCreate.model_validate(body)
        except ValidationError as exc:
            return _validation_error_response(exc)

        repository = get_repository()
        ml_service = get_ml_service()

        try:
            embedding = ml_service.embed_text(parsed.text)
            feedback = repository.create_feedback(parsed, embedding=embedding)
            feedback_count = repository.get_feedback_count()
            should_retrain = ml_service.should_retrain()

            payload = FeedbackResponse(
                feedback=feedback,
                should_retrain=should_retrain,
                feedback_count=feedback_count,
            )
            return Response(payload.model_dump(mode="json"), status=201)
        except Exception as exc:
            return Response({"detail": f"Failed to submit feedback: {exc}"}, status=500)

    def get(self, request):
        label_id = request.query_params.get("label_id")
        limit_raw = request.query_params.get("limit", "100")
        try:
            limit = int(limit_raw)
        except ValueError:
            return Response({"detail": "limit must be an integer"}, status=422)
        if limit < 1 or limit > 1000:
            return Response({"detail": "limit must be between 1 and 1000"}, status=422)

        repository = get_repository()
        feedback = repository.list_feedback(label_id=label_id)
        return Response([item.model_dump(mode="json") for item in feedback[:limit]])


class ModelStatusView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        status = get_ml_service().get_training_status()
        return Response(status.model_dump(mode="json"))


class ModelTrainView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        ml_service = get_ml_service()
        status = ml_service.get_training_status()

        if not status.ready_to_train:
            payload = TrainingResult(
                success=False,
                message=(
                    f"Not ready to train. Need {status.min_samples_required} positive samples "
                    f"(have {status.positive_samples}) and at least 2 labels (have {status.labels_count})"
                ),
                sample_count=status.sample_count,
            )
            return Response(payload.model_dump(mode="json"))

        result = ml_service.train_model()
        return Response(result.model_dump(mode="json"))
