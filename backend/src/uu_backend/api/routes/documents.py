"""Document retrieval endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from uu_backend.config import get_settings
from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.document import DocumentListResponse, DocumentResponse

router = APIRouter()
logger = logging.getLogger(__name__)


def get_original_file_path(document_id: str, file_type: str) -> Path | None:
    """Find the original file for a document."""
    settings = get_settings()
    storage_path = settings.file_storage_path

    # Map file types to extensions
    ext_map = {
        "pdf": ".pdf",
        "docx": ".docx",
        "doc": ".doc",
        "xlsx": ".xlsx",
        "xls": ".xls",
        "pptx": ".pptx",
        "ppt": ".ppt",
        "txt": ".txt",
        "md": ".md",
        "html": ".html",
        "csv": ".csv",
        "json": ".json",
        "xml": ".xml",
        "jpg": ".jpg",
        "jpeg": ".jpeg",
        "png": ".png",
        "gif": ".gif",
        "webp": ".webp",
        "eml": ".eml",
    }

    ext = ext_map.get(file_type.lower(), f".{file_type.lower()}")
    file_path = storage_path / f"{document_id}{ext}"

    if file_path.exists():
        return file_path

    # Try common extensions if the mapped one doesn't exist
    for extension in ext_map.values():
        alt_path = storage_path / f"{document_id}{extension}"
        if alt_path.exists():
            return alt_path

    return None


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents():
    """
    List all documents in the store.

    Returns summaries of all documents including metadata and chunk counts.
    """
    store = get_vector_store()
    sqlite_client = get_sqlite_client()
    documents = store.get_all_documents()
    
    # Enrich with classification data from SQLite
    for doc in documents:
        classification = sqlite_client.get_classification(doc.id)
        if classification:
            doc_type = sqlite_client.get_document_type(classification.document_type_id)
            if doc_type:
                doc.document_type = doc_type

    return DocumentListResponse(
        documents=documents,
        total=len(documents),
    )


@router.get("/documents/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str):
    """
    Get a specific document by ID.

    Returns the full document including content and all chunks.

    Raises 404 if document not found.
    """
    store = get_vector_store()
    document = store.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {document_id}",
        )

    return DocumentResponse(document=document)


@router.get("/documents/{document_id}/file")
async def get_document_file(document_id: str, download: bool = False):
    """
    Get the original file for a document.

    Returns the raw file as stored during ingestion.
    Useful for rendering PDFs, images, etc.

    Query params:
        download: If true, force download. Otherwise display inline.

    Raises 404 if document or file not found.
    """
    store = get_vector_store()
    document = store.get_document(document_id)

    if not document:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {document_id}",
        )

    file_path = get_original_file_path(document_id, document.file_type)

    if not file_path:
        raise HTTPException(
            status_code=404,
            detail=f"Original file not found for document: {document_id}",
        )

    # Determine media type
    media_types = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt": "application/vnd.ms-powerpoint",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".html": "text/html",
        ".csv": "text/csv",
        ".json": "application/json",
        ".xml": "application/xml",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".eml": "message/rfc822",
    }

    ext = file_path.suffix.lower()
    media_type = media_types.get(ext, "application/octet-stream")

    # Set content disposition: inline for viewing, attachment for download
    if download:
        content_disposition = f'attachment; filename="{document.filename}"'
    else:
        content_disposition = f'inline; filename="{document.filename}"'

    return FileResponse(
        path=file_path,
        media_type=media_type,
        headers={"Content-Disposition": content_disposition},
    )


@router.delete("/documents/{document_id}")
async def delete_document(document_id: str):
    """
    Delete a document by ID.

    Removes the document and all its chunks from the store.

    Raises 404 if document not found.
    """
    store = get_vector_store()
    neo4j_client = get_neo4j_client()
    document = store.get_document(document_id)

    if document:
        # Also delete the original file
        file_path = get_original_file_path(document_id, document.file_type)
        if file_path:
            file_path.unlink(missing_ok=True)

    deleted = store.delete_document(document_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Document not found: {document_id}",
        )

    graph_cleanup: dict[str, object]
    try:
        graph_cleanup = neo4j_client.delete_document_graph_data(document_id)
        valid_doc_ids = [doc.id for doc in store.get_all_documents()]
        reconcile_summary = neo4j_client.reconcile_documents(valid_doc_ids)
        graph_cleanup["reconcile"] = reconcile_summary
    except Exception as exc:
        logger.exception(
            "graph_document_delete_failed",
            extra={"document_id": document_id},
        )
        graph_cleanup = {"error": str(exc)}

    return {
        "status": "deleted",
        "document_id": document_id,
        "graph_cleanup": graph_cleanup,
    }


@router.post("/documents/{document_id}/reprocess")
async def reprocess_document(document_id: str):
    """
    Reprocess a document with the current converter.
    
    Useful after converter improvements to update existing documents.
    """
    from uu_backend.ingestion.converter import get_converter

    store = get_vector_store()
    document = store.get_document(document_id)

    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    # Get original file
    file_path = get_original_file_path(document_id, document.file_type)
    if not file_path:
        raise HTTPException(status_code=404, detail="Original file not found")

    try:
        # Re-convert the document
        converter = get_converter()
        with open(file_path, "rb") as f:
            result = converter.convert(f, document.filename)

        if not result.success:
            raise HTTPException(status_code=500, detail=f"Conversion failed: {result.error}")

        # Update document content in vector store
        store.update_document_content(document_id, result.content)

        return {
            "status": "reprocessed",
            "document_id": document_id,
            "content_length": len(result.content),
            "message": (
                "Document reprocessed successfully. "
                "Note: Existing annotations may have invalid offsets."
            ),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reprocessing failed: {str(e)}")
