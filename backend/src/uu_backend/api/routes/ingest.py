"""Document ingestion endpoints."""

import time
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, UploadFile

from uu_backend.config import get_settings
from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.extraction.entities import extract_entities
from uu_backend.extraction.relationships import store_entities_and_relationships
from uu_backend.ingestion.chunker import get_chunker
from uu_backend.ingestion.converter import get_converter
from uu_backend.ingestion.dates import extract_date
from uu_backend.models.document import Document, IngestResponse

router = APIRouter()


def process_entity_extraction(
    doc_id: str,
    content: str,
    date_extracted,
) -> None:
    """Background task to extract entities and store in Neo4j."""
    try:
        # Extract entities using LLM
        extracted = extract_entities(content, doc_id)

        # Store in Neo4j
        if extracted.entities or extracted.relationships:
            store_entities_and_relationships(
                entities=extracted.entities,
                relationships=extracted.relationships,
                document_id=doc_id,
                document_date=date_extracted,
            )
    except Exception:
        # Log error but don't fail the ingestion
        pass


def dispatch_entity_extraction(
    doc_id: str,
    content: str,
    date_extracted,
) -> None:
    """Dispatch entity extraction according to configured async executor."""
    settings = get_settings()
    executor = settings.async_executor.strip().lower()

    if executor == "celery":
        try:
            from uu_backend.tasks.extraction_tasks import process_entity_extraction_task

            date_iso = date_extracted.isoformat() if date_extracted else None
            process_entity_extraction_task.delay(doc_id=doc_id, content=content, date_extracted_iso=date_iso)
            return
        except Exception:
            # Fall back to in-process dispatch if broker/worker is unavailable.
            pass

    process_entity_extraction(doc_id=doc_id, content=content, date_extracted=date_extracted)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    files: Annotated[list[UploadFile], File(description="Documents to ingest")],
    background_tasks: BackgroundTasks,
):
    """
    Ingest one or more documents.

    Accepts multiple files, converts them to markdown, extracts dates,
    chunks the content, and stores in the vector database.

    Entity extraction runs in the background after ingestion.

    Supported formats: PDF, DOCX, XLSX, PPTX, HTML, TXT, MD, images, and more.
    """
    start_time = time.time()

    settings = get_settings()
    async_executor = settings.async_executor.strip().lower()
    converter = get_converter()
    chunker = get_chunker()
    vector_store = get_vector_store()
    neo4j_client = get_neo4j_client()

    documents_processed = 0
    chunks_created = 0
    document_ids: list[str] = []
    errors: list[str] = []

    for upload_file in files:
        filename = upload_file.filename or "unknown"

        # Check if file type is supported
        if not converter.is_supported(filename):
            errors.append(f"{filename}: Unsupported file type")
            continue

        try:
            # Generate document ID first (needed for file storage)
            doc_id = str(uuid.uuid4())

            # Save original file to disk
            file_ext = Path(filename).suffix.lower()
            original_file_path = settings.file_storage_path / f"{doc_id}{file_ext}"
            file_content = await upload_file.read()
            with open(original_file_path, "wb") as f:
                f.write(file_content)

            # Reset file position for conversion
            await upload_file.seek(0)

            # Convert document to markdown
            result = converter.convert(upload_file.file, filename)

            if not result.success:
                errors.append(f"{filename}: {result.error}")
                # Clean up saved file on conversion failure
                original_file_path.unlink(missing_ok=True)
                continue

            # Extract date from content
            date_extracted = extract_date(result.content)

            # Update metadata with extracted date
            result.metadata.date_extracted = date_extracted

            # Chunk the content
            chunks = chunker.chunk(
                content=result.content,
                document_id=doc_id,
                metadata={
                    "filename": filename,
                    "file_type": result.metadata.file_type,
                },
            )

            # Create document
            document = Document(
                id=doc_id,
                filename=filename,
                file_type=result.metadata.file_type,
                content=result.content,
                date_extracted=date_extracted,
                metadata=result.metadata,
                chunks=chunks,
            )

            # Store in vector database (for RAG/Q&A)
            vector_store.add_document(document)

            # Store document in Neo4j (for timeline/graph)
            neo4j_client.create_document(
                doc_id=doc_id,
                filename=filename,
                file_type=result.metadata.file_type,
                date_extracted=date_extracted,
                created_at=document.created_at,
            )

            # Queue/dispatch entity extraction
            if async_executor == "inline":
                background_tasks.add_task(
                    process_entity_extraction,
                    doc_id,
                    result.content,
                    date_extracted,
                )
            else:
                background_tasks.add_task(
                    dispatch_entity_extraction,
                    doc_id,
                    result.content,
                    date_extracted,
                )

            documents_processed += 1
            chunks_created += len(chunks)
            document_ids.append(doc_id)

        except Exception as e:
            errors.append(f"{filename}: {str(e)}")

        finally:
            # Reset file position for potential retry
            await upload_file.seek(0)

    processing_time = time.time() - start_time

    if documents_processed == 0 and errors:
        raise HTTPException(
            status_code=400,
            detail={"message": "All documents failed to process", "errors": errors},
        )

    return IngestResponse(
        status="success" if not errors else "partial",
        documents_processed=documents_processed,
        chunks_created=chunks_created,
        processing_time_seconds=round(processing_time, 2),
        document_ids=document_ids,
        errors=errors,
    )


@router.get("/ingest/status")
async def get_ingest_status():
    """
    Get current ingestion statistics.

    Returns counts of documents, chunks, and graph entities.
    """
    vector_store = get_vector_store()
    neo4j_client = get_neo4j_client()

    # Get Neo4j stats
    try:
        graph_stats = neo4j_client.get_stats()
    except Exception:
        graph_stats = {}

    return {
        "documents": vector_store.count(),
        "chunks": vector_store.chunk_count(),
        "graph": graph_stats,
    }
