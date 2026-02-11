"""Django API router for migrated endpoint groups."""

from django.urls import include, path

urlpatterns = [
    path("", include("uu_backend.django_api.urls")),
]
