"""Proxy views for evaluation endpoints."""

from uu_backend.django_api.fastapi_proxy import FastAPIProxyView


class EvaluationRootProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/evaluation"


class EvaluationPrefixProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/evaluation/{subpath}"

