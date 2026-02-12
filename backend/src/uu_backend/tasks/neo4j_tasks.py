"""Celery tasks for Neo4j indexing."""

import logging
from pathlib import Path

from celery import shared_task

from uu_backend.config import get_settings
from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.extraction.entities import extract_entities
from uu_backend.extraction.relationships import store_entities_and_relationships
from uu_backend.services.graph_ingestion_service import get_graph_ingestion_service

logger = logging.getLogger(__name__)


def _resolve_original_file_path(document_id: str, file_type: str) -> str | None:
    """Resolve stored source file path for a document id."""
    settings = get_settings()
    storage_path = settings.file_storage_path
    normalized_type = (file_type or "").strip().lower()

    if normalized_type:
        candidate = storage_path / f"{document_id}.{normalized_type}"
        if candidate.exists():
            return str(candidate)

    for match in Path(storage_path).glob(f"{document_id}.*"):
        if match.is_file():
            return str(match)
    return None


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
    graph_service = get_graph_ingestion_service()
    try:
        graph_summary = graph_service.extract_and_store_entities(
            doc_id=document.id,
            content=document.content,
            document_date=document.date_extracted,
            filename=document.filename,
            file_type=document.file_type,
            file_path=_resolve_original_file_path(document.id, document.file_type),
            created_at=document.created_at,
        )

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
        (
            "Neo4j indexing complete for %s "
            "(graph_chunks_entities=%d, entities=%d, relationships=%d)"
        ),
        document.id,
        graph_summary.entities_written,
        len(extracted.entities),
        len(extracted.relationships),
    )

    return {
        "status": "indexed",
        "document_id": document.id,
        "graphrag_entities": graph_summary.entities_written,
        "entities": len(extracted.entities),
        "relationships": len(extracted.relationships),
    }
