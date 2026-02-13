"""DRF views for timeline endpoints."""

from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.repositories.document_repository import get_document_repository


class TimelineView(APIView):
    """Timeline endpoint preserving API contract."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        start_date_raw = request.query_params.get("start_date")
        end_date_raw = request.query_params.get("end_date")

        try:
            start_date = date.fromisoformat(start_date_raw) if start_date_raw else None
        except ValueError:
            return Response({"detail": "Invalid start_date. Use ISO date format YYYY-MM-DD."}, status=422)

        try:
            end_date = date.fromisoformat(end_date_raw) if end_date_raw else None
        except ValueError:
            return Response({"detail": "Invalid end_date. Use ISO date format YYYY-MM-DD."}, status=422)

        timeline = get_document_repository().get_timeline(start_date=start_date, end_date=end_date)
        return Response(timeline.model_dump(mode="json"))


class TimelineRangeView(APIView):
    """Timeline range endpoint preserving API contract."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        timeline = get_document_repository().get_timeline()
        return Response(
            {
                "earliest": timeline.date_range.earliest,
                "latest": timeline.date_range.latest,
                "total_documents": timeline.total_documents,
            }
        )
