"""DRF views for health endpoints."""

from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend import __version__
from uu_backend.llm.openai_client import get_openai_client
from uu_backend.repositories.document_repository import get_document_repository


class HealthView(APIView):
    """Health status endpoint preserving API response contract."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        try:
            document_repo = get_document_repository()
            doc_count = document_repo.count()
            db_status = "connected"
        except Exception as exc:
            doc_count = 0
            db_status = f"error: {exc}"

        try:
            openai_client = get_openai_client()
            openai_status = "available" if openai_client.is_available() else "not configured"
        except Exception:  # nosec B110
            openai_status = "not configured"

        all_connected = db_status == "connected"

        return Response(
            {
                "status": "healthy" if all_connected else "degraded",
                "version": __version__,
                "services": {
                    "database": db_status,
                    "openai": openai_status,
                },
                "stats": {
                    "documents": doc_count,
                },
            }
        )
