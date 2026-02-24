"""URL routes for Contextual Retrieval API."""

from django.urls import path

from . import views

urlpatterns = [
    path(
        "search",
        views.SearchView.as_view(),
        name="search",
    ),
]
