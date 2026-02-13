"""DRF views for suggestions and ML feedback endpoints."""

from pydantic import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.models.feedback import (
    FeedbackCreate,
    FeedbackResponse,
    TrainingResult,
    TrainingStatus,
)
from uu_backend.models.suggestion import SuggestionRequest
from uu_backend.repositories import get_repository
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

        document_repo = get_document_repository()
        document = document_repo.get_document(document_id)
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

        try:
            feedback = repository.create_feedback(parsed, embedding=None)
            feedback_count = repository.get_feedback_count()

            payload = FeedbackResponse(
                feedback=feedback,
                should_retrain=False,
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
        status = TrainingStatus(
            is_trained=False,
            sample_count=0,
            min_samples_required=20,
            ready_to_train=False,
        )
        return Response(status.model_dump(mode="json"))


class ModelTrainView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        payload = TrainingResult(
            success=False,
            message="ML training is disabled (embeddings removed)",
            sample_count=0,
        )
        return Response(payload.model_dump(mode="json"))
