"""Celery task modules."""

from .extraction_tasks import process_entity_extraction_task

__all__ = ["process_entity_extraction_task"]
