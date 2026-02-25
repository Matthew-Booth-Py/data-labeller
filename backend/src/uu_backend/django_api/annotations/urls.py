"""URL routing for annotations API."""

from django.urls import path

from .views import (
    AnnotationSuggestionView,
    ApproveAnnotationView,
    GroundTruthAnnotationDetailView,
    GroundTruthAnnotationListView,
    RejectAnnotationView,
)

urlpatterns = [
    # Ground truth annotations for a document
    path(
        "documents/<str:document_id>/ground-truth",
        GroundTruthAnnotationListView.as_view(),
        name="ground-truth-list",
    ),
    # AI annotation suggestions
    path(
        "documents/<str:document_id>/suggest-annotations",
        AnnotationSuggestionView.as_view(),
        name="suggest-annotations",
    ),
    # Individual annotation operations
    path(
        "annotations/<str:annotation_id>",
        GroundTruthAnnotationDetailView.as_view(),
        name="annotation-detail",
    ),
    # Approve/reject AI suggestions
    path(
        "annotations/<str:annotation_id>/approve",
        ApproveAnnotationView.as_view(),
        name="approve-annotation",
    ),
    path(
        "annotations/<str:annotation_id>/reject",
        RejectAnnotationView.as_view(),
        name="reject-annotation",
    ),
]
