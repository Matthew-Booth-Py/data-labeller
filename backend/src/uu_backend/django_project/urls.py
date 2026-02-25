"""URL configuration for migration Django app."""

from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from uu_backend.django_api.health.views import HealthView

urlpatterns = [
    path("health", HealthView.as_view(), name="root-health"),
    path("api/v1/", include("uu_backend.django_project.api_router")),
    path("api/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("docs", SpectacularSwaggerView.as_view(url_name="api-schema"), name="root-docs"),
    path("redoc", SpectacularRedocView.as_view(url_name="api-schema"), name="root-redoc"),
]
