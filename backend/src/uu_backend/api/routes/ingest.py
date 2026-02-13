"""Document ingestion endpoints."""

import logging
import time
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile

from uu_backend.config import get_settings
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.ingestion.converter import get_converter
from uu_backend.ingestion.dates import extract_date
from uu_backend.models.document import Document, IngestResponse

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(
    files: Annotated[list[UploadFile], File(description="Documents to ingest")],
):
    """
    Ingest one or more documents.

    Accepts multiple files, converts them to markdown, extracts dates,
    chunks the content, and stores in the vector database.

    Supported formats: PDF, DOCX, XLSX, PPTX, HTML, TXT, MD, images, and more.
    """
    start_time = time.time()

    settings = get_settings()
    converter = get_converter()
    document_repo = get_document_repository()

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

            # Create document
            document = Document(
                id=doc_id,
                filename=filename,
                file_type=result.metadata.file_type,
                content=result.content,
                date_extracted=date_extracted,
                metadata=result.metadata,
                chunks=[],
            )

            # Store document in database
            try:
                document_repo.add_document(document)
                logger.info("Document %s stored successfully", doc_id)
            except Exception as store_error:
                # Clean up on failure
                original_file_path.unlink(missing_ok=True)
                errors.append(f"{filename}: Failed to store: {store_error}")
                logger.exception("Failed to store document %s", filename)
                continue

            documents_processed += 1
            document_ids.append(doc_id)

        except Exception as e:
            errors.append(f"{filename}: {str(e)}")
            logger.exception("Document ingestion failed for %s", filename)

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
        chunks_created=0,
        processing_time_seconds=round(processing_time, 2),
        document_ids=document_ids,
        errors=errors,
    )


@router.get("/ingest/status")
async def get_ingest_status():
    """
    Get current ingestion statistics.

    Returns counts of documents.
    """
    document_repo = get_document_repository()

    return {
        "documents": document_repo.count(),
        "chunks": 0,
    }
