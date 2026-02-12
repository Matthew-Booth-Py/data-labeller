"""Celery tasks for Neo4j indexing."""

import logging

from celery import shared_task

from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.extraction.entities import extract_entities
from uu_backend.extraction.relationships import store_entities_and_relationships

logger = logging.getLogger(__name__)


@shared_task(
    name="uu_backend.tasks.neo4j.index_document",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
    retry_kwargs={"max_retries": 3},
)
def index_document_in_neo4j_task(document_id: str) -> dict[str, int | str]:
    """Index a document and its extracted entities/relationships in Neo4j."""
    vector_store = get_vector_store()
    document = vector_store.get_document(document_id)
    if not document:
        logger.warning("Celery Neo4j index skipped: document %s was not found", document_id)
        return {"status": "missing_document", "document_id": document_id}

    neo4j_client = get_neo4j_client()
    try:
        extracted = extract_entities(document.content, document.id)
        neo4j_client.create_document(
            doc_id=document.id,
            filename=document.filename,
            file_type=document.file_type,
            date_extracted=document.date_extracted,
            created_at=document.created_at,
        )
        if extracted.entities or extracted.relationships:
            store_entities_and_relationships(
                entities=extracted.entities,
                relationships=extracted.relationships,
                document_id=document.id,
                document_date=document.date_extracted,
            )
        else:
            logger.warning(
                "Neo4j indexing extracted no entities/relationships for document %s",
                document.id,
            )
    except Exception:
        logger.exception("Neo4j indexing failed for %s", document.id)
        try:
            neo4j_client.delete_document_graph_data(document.id)
        except Exception:
            logger.exception("Neo4j rollback failed for %s", document.id)
        raise

    logger.info(
        "Neo4j indexing complete for %s (entities=%d, relationships=%d)",
        document.id,
        len(extracted.entities),
        len(extracted.relationships),
    )

    return {
        "status": "indexed",
        "document_id": document.id,
        "entities": len(extracted.entities),
        "relationships": len(extracted.relationships),
    }
