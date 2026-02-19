"""Celery task modules."""

from uu_backend.tasks.azure_di_tasks import analyze_document_with_azure_di
from uu_backend.tasks.contextual_retrieval_tasks import (
    delete_document_from_retrieval_index,
    index_document_for_retrieval,
    reindex_all_documents,
)
from uu_backend.tasks.evaluation_tasks import run_evaluation_task

__all__ = [
    "analyze_document_with_azure_di",
    "run_evaluation_task",
    "index_document_for_retrieval",
    "delete_document_from_retrieval_index",
    "reindex_all_documents",
]
