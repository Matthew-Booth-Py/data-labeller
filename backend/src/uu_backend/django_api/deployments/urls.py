"""URL routes for deployment endpoints."""

from django.urls import re_path

from .views import DeploymentsPrefixView

urlpatterns = [
    re_path(
        r"^deployments/(?P<subpath>.+)$",
        DeploymentsPrefixView.as_view(),
        name="deployments-prefix",
    ),
]
