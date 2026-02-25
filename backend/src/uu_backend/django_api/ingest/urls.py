"""URL routes for ingest endpoints."""

from django.urls import path

from .views import IngestStatusView, IngestView

urlpatterns = [
    path("ingest", IngestView.as_view(), name="ingest"),
    path("ingest/status", IngestStatusView.as_view(), name="ingest-status"),
]
