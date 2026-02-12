from django.urls import path

from .views import (
    GraphDeleteDbView,
    GraphEntitiesView,
    GraphEntityDetailView,
    GraphIndexDocumentsView,
    GraphIndexingStatusView,
    GraphIndexMissingView,
    GraphRemoveDocumentView,
    GraphStatsView,
    GraphTimelineView,
    GraphView,
)

urlpatterns = [
    path("graph", GraphView.as_view(), name="graph"),
    path("graph/entities", GraphEntitiesView.as_view(), name="graph-entities"),
    path("graph/entities/<str:entity_id>", GraphEntityDetailView.as_view(), name="graph-entity-detail"),
    path("graph/timeline", GraphTimelineView.as_view(), name="graph-timeline"),
    path("graph/stats", GraphStatsView.as_view(), name="graph-stats"),
    path("graph/indexing/status", GraphIndexingStatusView.as_view(), name="graph-indexing-status"),
    path("graph/indexing/index-missing", GraphIndexMissingView.as_view(), name="graph-indexing-index-missing"),
    path("graph/indexing/index-documents", GraphIndexDocumentsView.as_view(), name="graph-indexing-index-documents"),
    path("graph/indexing/delete-db", GraphDeleteDbView.as_view(), name="graph-indexing-delete-db"),
    path("graph/indexing/remove", GraphRemoveDocumentView.as_view(), name="graph-indexing-remove"),
]
