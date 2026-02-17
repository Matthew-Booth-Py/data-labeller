"""Top-level URLs for migrated Django API endpoints."""

from django.urls import include, path

urlpatterns = [
    path("", include("uu_backend.django_api.health.urls")),
    path("", include("uu_backend.django_api.documents.urls")),
    path("", include("uu_backend.django_api.providers.urls")),
    path("", include("uu_backend.django_api.ingest.urls")),
    path("", include("uu_backend.django_api.tutorial.urls")),
    path("", include("uu_backend.django_api.taxonomy.urls")),
    path("", include("uu_backend.django_api.deployments.urls")),
]
