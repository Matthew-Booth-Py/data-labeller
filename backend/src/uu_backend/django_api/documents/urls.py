from django.urls import path

from .views import (
    DocumentDetailView,
    DocumentFileView,
    DocumentReprocessView,
    DocumentsListView,
    DocumentReindexRetrievalView,
)

urlpatterns = [
    path("documents", DocumentsListView.as_view(), name="documents-list"),
    path("documents/<str:document_id>", DocumentDetailView.as_view(), name="documents-detail"),
    path("documents/<str:document_id>/file", DocumentFileView.as_view(), name="documents-file"),
    path("documents/<str:document_id>/reprocess", DocumentReprocessView.as_view(), name="documents-reprocess"),
    path("documents/<str:document_id>/reindex-retrieval", DocumentReindexRetrievalView.as_view(), name="documents-reindex-retrieval"),
]
