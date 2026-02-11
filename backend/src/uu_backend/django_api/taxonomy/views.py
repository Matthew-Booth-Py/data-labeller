"""Proxy views for taxonomy endpoints."""

from uu_backend.django_api.fastapi_proxy import FastAPIProxyView


class TaxonomyPrefixProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/taxonomy/{subpath}"


class ClassifyDocumentProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/documents/{document_id}/classify"


class AutoClassifyDocumentProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/documents/{document_id}/auto-classify"


class DocumentClassificationProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/documents/{document_id}/classification"


class ExtractDocumentProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/documents/{document_id}/extract"


class DocumentExtractionProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/documents/{document_id}/extraction"

