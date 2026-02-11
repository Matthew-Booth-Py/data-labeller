"""Top-level URLs for migrated Django API endpoints."""

from django.urls import include, path

urlpatterns = [
    path("", include("uu_backend.django_api.health.urls")),
    path("", include("uu_backend.django_api.timeline.urls")),
    path("", include("uu_backend.django_api.search.urls")),
    path("", include("uu_backend.django_api.documents.urls")),
    path("", include("uu_backend.django_api.graph.urls")),
    path("", include("uu_backend.django_api.providers.urls")),
]
