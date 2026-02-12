"""Celery task modules."""

from .extraction_tasks import process_entity_extraction_task
from .neo4j_tasks import index_document_in_neo4j_task

__all__ = [
    "process_entity_extraction_task",
    "index_document_in_neo4j_task",
]
