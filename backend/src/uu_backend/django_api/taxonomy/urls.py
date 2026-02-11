"""URL routes for taxonomy endpoints."""

from django.urls import path, re_path

from .views import (
    AutoClassifyDocumentProxyView,
    ClassifyDocumentProxyView,
    DocumentClassificationProxyView,
    DocumentExtractionProxyView,
    ExtractDocumentProxyView,
    TaxonomyPrefixProxyView,
)

urlpatterns = [
    re_path(
        r"^taxonomy/(?P<subpath>.+)$",
        TaxonomyPrefixProxyView.as_view(),
        name="taxonomy-prefix",
    ),
    path(
        "documents/<str:document_id>/classify",
        ClassifyDocumentProxyView.as_view(),
        name="taxonomy-document-classify",
    ),
    path(
        "documents/<str:document_id>/auto-classify",
        AutoClassifyDocumentProxyView.as_view(),
        name="taxonomy-document-auto-classify",
    ),
    path(
        "documents/<str:document_id>/classification",
        DocumentClassificationProxyView.as_view(),
        name="taxonomy-document-classification",
    ),
    path(
        "documents/<str:document_id>/extract",
        ExtractDocumentProxyView.as_view(),
        name="taxonomy-document-extract",
    ),
    path(
        "documents/<str:document_id>/extraction",
        DocumentExtractionProxyView.as_view(),
        name="taxonomy-document-extraction",
    ),
]

