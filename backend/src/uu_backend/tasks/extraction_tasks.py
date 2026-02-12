"""Background extraction tasks for migration phase 2."""

import logging

from celery import shared_task

from uu_backend.extraction.entities import extract_entities
from uu_backend.extraction.relationships import store_entities_and_relationships

logger = logging.getLogger(__name__)


def process_entity_extraction(doc_id: str, content: str, date_extracted) -> None:
    """Extract entities/relationships and persist into Neo4j."""
    try:
        extracted = extract_entities(content, doc_id)
        if extracted.entities or extracted.relationships:
            store_entities_and_relationships(
                entities=extracted.entities,
                relationships=extracted.relationships,
                document_id=doc_id,
                document_date=date_extracted,
            )
    except Exception:
        logger.exception("Entity extraction task failed for document %s", doc_id)
        raise


@shared_task(name="uu_backend.tasks.process_entity_extraction")
def process_entity_extraction_task(doc_id: str, content: str, date_extracted_iso: str | None = None) -> None:
    """Celery wrapper for entity extraction side effects."""
    from datetime import datetime

    parsed_date = None
    if date_extracted_iso:
        try:
            parsed_date = datetime.fromisoformat(date_extracted_iso)
        except ValueError:
            parsed_date = None

    process_entity_extraction(doc_id=doc_id, content=content, date_extracted=parsed_date)
