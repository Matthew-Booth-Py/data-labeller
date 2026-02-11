"""URL routes for annotation endpoints."""

from django.urls import path, re_path

from .views import (
    AnnotationsPrefixView,
    AnnotationsRootView,
    DocumentAnnotationsView,
    DocumentAnnotationStatsView,
    DocumentExportView,
    DocumentSuggestAnnotationsView,
    LabelsPrefixView,
    LabelsRootView,
)

urlpatterns = [
    path("labels", LabelsRootView.as_view(), name="labels-root"),
    re_path(r"^labels/(?P<subpath>.+)$", LabelsPrefixView.as_view(), name="labels-prefix"),
    path("annotations", AnnotationsRootView.as_view(), name="annotations-root"),
    re_path(
        r"^annotations/(?P<subpath>.+)$",
        AnnotationsPrefixView.as_view(),
        name="annotations-prefix",
    ),
    path(
        "documents/<str:document_id>/annotations",
        DocumentAnnotationsView.as_view(),
        name="document-annotations",
    ),
    path(
        "documents/<str:document_id>/annotations/stats",
        DocumentAnnotationStatsView.as_view(),
        name="document-annotation-stats",
    ),
    path(
        "documents/<str:document_id>/export",
        DocumentExportView.as_view(),
        name="document-export",
    ),
    path(
        "documents/<str:document_id>/suggest-annotations",
        DocumentSuggestAnnotationsView.as_view(),
        name="document-suggest-annotations",
    ),
]
