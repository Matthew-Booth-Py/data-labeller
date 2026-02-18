"""Celery task modules."""

from uu_backend.tasks.azure_di_tasks import analyze_document_with_azure_di

__all__ = [
    "analyze_document_with_azure_di",
]
