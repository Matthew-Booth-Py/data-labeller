"""Celery tasks for Neo4j indexing."""

import logging
from datetime import datetime
from pathlib import Path

from celery import shared_task

from uu_backend.config import get_settings
from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.extraction.entities import extract_entities
from uu_backend.extraction.relationships import store_entities_and_relationships
from uu_backend.ingestion.converter import get_converter
from uu_backend.ingestion.dates import extract_date
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


def _load_document_from_file(document_id: str) -> dict | None:
    """
    Load document content from the original file on disk.
    
    This is used when the document doesn't exist in Neo4j yet (first-time indexing).
    
    Returns:
        dict with doc_id, content, filename, file_type, date_extracted, created_at
        or None if file not found or conversion failed
    """
    settings = get_settings()
    storage_path = settings.file_storage_path
    
    # Find the original file
    file_path = None
    for match in Path(storage_path).glob(f"{document_id}.*"):
        if match.is_file():
            file_path = match
            break
    
    if not file_path:
        logger.warning("Original file not found for document %s", document_id)
        return None
    
    # Convert the file
    converter = get_converter()
    try:
        with open(file_path, "rb") as f:
            result = converter.convert(f, file_path.name)
        
        if not result.success:
            logger.error("Conversion failed for %s: %s", document_id, result.error)
            return None
        
        # Extract date from content
        date_extracted = extract_date(result.content)
        
        return {
            "doc_id": document_id,
            "content": result.content,
            "filename": file_path.name,
            "file_type": file_path.suffix.lstrip(".").lower(),
            "date_extracted": date_extracted,
            "created_at": datetime.utcnow(),
            "file_path": str(file_path),
        }
    except Exception as e:
        logger.exception("Failed to load document %s from file: %s", document_id, e)
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
    
    # If document not found in Neo4j, try to load from the original file
    # This handles the case where the document is being indexed for the first time
    doc_id = document_id
    content = None
    filename = None
    file_type = None
    date_extracted = None
    created_at = None
    file_path = None
    
    if document:
        # Document exists in Neo4j, use its data
        doc_id = document.id
        content = document.content
        filename = document.filename
        file_type = document.file_type
        date_extracted = document.date_extracted
        created_at = document.created_at
        file_path = _resolve_original_file_path(doc_id, file_type)
    else:
        # Document not in Neo4j yet, load from file
        logger.info("Document %s not found in Neo4j, loading from file", document_id)
        doc_data = _load_document_from_file(document_id)
        if not doc_data:
            logger.warning("Celery Neo4j index skipped: document %s could not be loaded", document_id)
            return {"status": "missing_document", "document_id": document_id}
        
        doc_id = doc_data["doc_id"]
        content = doc_data["content"]
        filename = doc_data["filename"]
        file_type = doc_data["file_type"]
        date_extracted = doc_data["date_extracted"]
        created_at = doc_data["created_at"]
        file_path = doc_data["file_path"]

    neo4j_client = get_neo4j_client()
    graph_service = get_graph_ingestion_service()
    try:
        graph_summary = graph_service.extract_and_store_entities(
            doc_id=doc_id,
            content=content,
            document_date=date_extracted,
            filename=filename,
            file_type=file_type,
            file_path=file_path,
            created_at=created_at,
        )

        extracted = extract_entities(content, doc_id)
        neo4j_client.create_document(
            doc_id=doc_id,
            filename=filename,
            file_type=file_type,
            date_extracted=date_extracted,
            created_at=created_at,
        )
        if extracted.entities or extracted.relationships:
            store_entities_and_relationships(
                entities=extracted.entities,
                relationships=extracted.relationships,
                document_id=doc_id,
                document_date=date_extracted,
            )
        else:
            logger.warning(
                "Neo4j indexing extracted no entities/relationships for document %s",
                doc_id,
            )
    except Exception:
        logger.exception("Neo4j indexing failed for %s", doc_id)
        try:
            neo4j_client.delete_document_graph_data(doc_id)
        except Exception:
            logger.exception("Neo4j rollback failed for %s", doc_id)
        raise

    # Mark document as fully indexed
    neo4j_client.mark_document_indexed(doc_id)

    logger.info(
        (
            "Neo4j indexing complete for %s "
            "(graph_chunks_entities=%d, entities=%d, relationships=%d)"
        ),
        doc_id,
        graph_summary.entities_written,
        len(extracted.entities),
        len(extracted.relationships),
    )

    return {
        "status": "indexed",
        "document_id": doc_id,
        "graphrag_entities": graph_summary.entities_written,
        "entities": len(extracted.entities),
        "relationships": len(extracted.relationships),
    }
