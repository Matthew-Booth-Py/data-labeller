"""URL routes for annotation endpoints."""

from django.urls import path, re_path

from .views import (
    AnnotationsPrefixProxyView,
    AnnotationsRootProxyView,
    DocumentAnnotationsProxyView,
    DocumentAnnotationStatsProxyView,
    DocumentExportProxyView,
    DocumentSuggestAnnotationsProxyView,
    LabelsPrefixProxyView,
    LabelsRootProxyView,
)

urlpatterns = [
    path("labels", LabelsRootProxyView.as_view(), name="labels-root"),
    re_path(r"^labels/(?P<subpath>.+)$", LabelsPrefixProxyView.as_view(), name="labels-prefix"),
    path("annotations", AnnotationsRootProxyView.as_view(), name="annotations-root"),
    re_path(
        r"^annotations/(?P<subpath>.+)$",
        AnnotationsPrefixProxyView.as_view(),
        name="annotations-prefix",
    ),
    path(
        "documents/<str:document_id>/annotations",
        DocumentAnnotationsProxyView.as_view(),
        name="document-annotations",
    ),
    path(
        "documents/<str:document_id>/annotations/stats",
        DocumentAnnotationStatsProxyView.as_view(),
        name="document-annotation-stats",
    ),
    path(
        "documents/<str:document_id>/export",
        DocumentExportProxyView.as_view(),
        name="document-export",
    ),
    path(
        "documents/<str:document_id>/suggest-annotations",
        DocumentSuggestAnnotationsProxyView.as_view(),
        name="document-suggest-annotations",
    ),
]

