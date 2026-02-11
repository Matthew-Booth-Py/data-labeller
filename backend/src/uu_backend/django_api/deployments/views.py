"""Proxy views for deployment endpoints."""

from uu_backend.django_api.fastapi_proxy import FastAPIProxyView


class DeploymentsPrefixProxyView(FastAPIProxyView):
    target_path_template = "/api/v1/deployments/{subpath}"

