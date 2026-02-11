"""URL routes for taxonomy endpoints."""

from django.urls import path, re_path

from .views import (
    AutoClassifyDocumentView,
    ClassifyDocumentView,
    DocumentClassificationView,
    DocumentExtractionView,
    ExtractDocumentView,
    TaxonomyPrefixView,
)

urlpatterns = [
    re_path(
        r"^taxonomy/(?P<subpath>.+)$",
        TaxonomyPrefixView.as_view(),
        name="taxonomy-prefix",
    ),
    path(
        "documents/<str:document_id>/classify",
        ClassifyDocumentView.as_view(),
        name="taxonomy-document-classify",
    ),
    path(
        "documents/<str:document_id>/auto-classify",
        AutoClassifyDocumentView.as_view(),
        name="taxonomy-document-auto-classify",
    ),
    path(
        "documents/<str:document_id>/classification",
        DocumentClassificationView.as_view(),
        name="taxonomy-document-classification",
    ),
    path(
        "documents/<str:document_id>/extract",
        ExtractDocumentView.as_view(),
        name="taxonomy-document-extract",
    ),
    path(
        "documents/<str:document_id>/extraction",
        DocumentExtractionView.as_view(),
        name="taxonomy-document-extraction",
    ),
]
