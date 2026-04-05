"""Compatibility facade over the PDF-only intelligent retrieval service."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.pdf_retrieval import get_pdf_retrieval_service

from .models import SearchResult


class ContextualRetrievalService:
    def __init__(self, *args: Any, **kwargs: Any):
        self._pdf_service = get_pdf_retrieval_service()

    def index_document(
        self,
        document_id: str,
        content: str | None = None,
        metadata: dict | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> int:
        document = get_document_repository().get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        if (document.file_type or "").lower() != "pdf":
            raise ValueError("PDF-only retrieval is supported. Reindexing requires a PDF document.")
        if not document.file_path:
            raise ValueError(f"Document {document_id} has no stored file path")

        return self._pdf_service.index_document(
            document_id=document_id,
            file_path=str(Path(document.file_path)),
            filename=document.filename,
            progress_callback=progress_callback,
        )

    def search(
        self,
        query: str,
        top_k: int = 20,
        filter_doc_id: str | None = None,
        use_reranking: bool = True,
        asset_types: set[str] | None = None,
    ) -> list[SearchResult]:
        return self._pdf_service.search(
            query=query,
            top_k=top_k,
            filter_doc_id=filter_doc_id,
            asset_types=asset_types,
        )

    def search_for_extraction(
        self,
        queries: list[str],
        top_k_per_query: int = 10,
        filter_doc_id: str | None = None,
        asset_types: set[str] | None = None,
    ) -> list[SearchResult]:
        if not filter_doc_id:
            raise ValueError("PDF extraction retrieval requires a specific document_id")
        return self._pdf_service.search_for_extraction(
            queries=queries,
            top_k_per_query=top_k_per_query,
            filter_doc_id=filter_doc_id,
            asset_types=asset_types,
        )

    def delete_document(self, document_id: str) -> dict[str, int]:
        return self._pdf_service.delete_document(document_id)

    def get_document_chunks(self, document_id: str) -> list[dict[str, Any]]:
        return self._pdf_service.get_document_chunks(document_id)

    def get_stats(self) -> dict[str, Any]:
        return self._pdf_service.get_stats()


_service_instance: ContextualRetrievalService | None = None


def get_contextual_retrieval_service() -> ContextualRetrievalService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ContextualRetrievalService()
    return _service_instance
