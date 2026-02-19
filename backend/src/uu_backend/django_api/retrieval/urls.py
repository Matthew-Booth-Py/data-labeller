"""URL routes for Contextual Retrieval API."""

from django.urls import path

from . import views

urlpatterns = [
    path(
        "api/v1/search",
        views.SearchView.as_view(),
        name="search",
    ),
    path(
        "api/v1/retrieval/index/<str:document_id>",
        views.IndexDocumentView.as_view(),
        name="index_document",
    ),
    path(
        "api/v1/retrieval/stats",
        views.RetrievalStatsView.as_view(),
        name="retrieval_stats",
    ),
    path(
        "api/v1/retrieval/documents/<str:document_id>/chunks",
        views.DocumentChunksView.as_view(),
        name="document_chunks",
    ),
]
