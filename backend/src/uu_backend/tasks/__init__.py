"""Celery task modules."""

from uu_backend.tasks.azure_di_tasks import analyze_document_with_azure_di
from uu_backend.tasks.evaluation_tasks import run_evaluation_task

__all__ = [
    "analyze_document_with_azure_di",
    "run_evaluation_task",
]
