"""Proxy views for annotations endpoints."""

from uu_backend.django_api.fastapi_proxy import FastAPIProxyView


class LabelsPrefixProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/labels/{subpath}"


class LabelsRootProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/labels"


class AnnotationsPrefixProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/annotations/{subpath}"


class AnnotationsRootProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/annotations"


class DocumentAnnotationsProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/documents/{document_id}/annotations"


class DocumentAnnotationStatsProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/documents/{document_id}/annotations/stats"


class DocumentExportProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/documents/{document_id}/export"


class DocumentSuggestAnnotationsProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/documents/{document_id}/suggest-annotations"

