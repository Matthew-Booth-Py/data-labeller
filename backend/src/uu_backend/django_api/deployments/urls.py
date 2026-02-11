"""URL routes for deployment endpoints."""

from django.urls import re_path

from .views import DeploymentsPrefixProxyView

urlpatterns = [
    re_path(
        r"^deployments/(?P<subpath>.+)$",
        DeploymentsPrefixProxyView.as_view(),
        name="deployments-prefix",
    ),
]

