"""URL routes for Contextual Retrieval API."""

from django.urls import path

from . import views

urlpatterns = [
    path(
        "search",
        views.SearchView.as_view(),
        name="search",
    ),
    path(
        "retrieval/index/<str:document_id>",
        views.IndexDocumentView.as_view(),
        name="index_document",
    ),
    path(
        "retrieval/stats",
        views.RetrievalStatsView.as_view(),
        name="retrieval_stats",
    ),
    path(
        "retrieval/documents/<str:document_id>/chunks",
        views.DocumentChunksView.as_view(),
        name="document_chunks",
    ),
]
