from django.urls import path

from .views import (
    GraphEntitiesView,
    GraphEntityDetailView,
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
]
