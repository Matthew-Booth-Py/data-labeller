"""Celery tasks for Contextual Retrieval indexing."""

import logging

from celery import shared_task

from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.contextual_retrieval import get_contextual_retrieval_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def index_document_for_retrieval(self, document_id: str):
    """
    Index a document for contextual retrieval.
    
    This task:
    1. Loads the document content from the database
    2. Uses Azure DI content if available (better quality)
    3. Chunks the document
    4. Generates context for each chunk using LLM
    5. Generates embeddings
    6. Stores in vector DB and BM25 index
    
    Args:
        document_id: Document ID to index
    """
    from uu_backend.django_data.models import DocumentModel
    
    try:
        logger.info(f"Starting contextual retrieval indexing for document {document_id}")
        
        # Update status to processing and reset progress
        doc_model = DocumentModel.objects.get(id=document_id)
        doc_model.retrieval_index_status = "processing"
        doc_model.retrieval_index_progress = 0
        doc_model.retrieval_index_total = None
        doc_model.save()
        
        doc_repo = get_document_repository()
        document = doc_repo.get_document(document_id)
        
        if not document:
            logger.error(f"Document {document_id} not found")
            doc_model.retrieval_index_status = "failed"
            doc_model.save()
            return {"status": "error", "message": "Document not found"}
        
        # Extract content using pdfplumber for PDFs
        content = None
        
        # Try pdfplumber first for PDFs
        if document.file_type.lower() == 'pdf':
            from uu_backend.config import get_settings
            from pathlib import Path
            import pdfplumber
            
            settings = get_settings()
            file_path = settings.file_storage_path / f"{document_id}.pdf"
            
            if file_path.exists():
                try:
                    logger.info(f"Extracting content from PDF using pdfplumber: {file_path}")
                    with pdfplumber.open(file_path) as pdf:
                        pages_text = []
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                pages_text.append(page_text)
                        content = "\n\n".join(pages_text)
                        logger.info(f"Extracted {len(content)} chars from {len(pages_text)} pages using pdfplumber")
                except Exception as e:
                    logger.warning(f"Failed to extract with pdfplumber: {e}")
        
        # Fall back to Azure DI content if available
        if not content or not content.strip():
            if doc_model.azure_di_analysis and doc_model.azure_di_status == "completed":
                content = doc_model.azure_di_analysis.get("content", "")
                if content:
                    logger.info(f"Using Azure DI content for {document_id} ({len(content)} chars)")
        
        # Fall back to standard document content
        if not content or not content.strip():
            content = document.content
            if content:
                logger.info(f"Using standard document content for {document_id} ({len(content)} chars)")
        
        if not content or not content.strip():
            logger.warning(f"Document {document_id} has no content to index")
            doc_model.retrieval_index_status = "completed"
            doc_model.retrieval_chunks_count = 0
            doc_model.save()
            return {"status": "skipped", "message": "No content to index"}
        
        service = get_contextual_retrieval_service()
        
        # Delete any existing index for this document before re-indexing
        try:
            deleted = service.delete_document(document_id)
            if deleted.get("vector_store", 0) > 0 or deleted.get("bm25_index", 0) > 0:
                logger.info(f"Cleaned up existing index for {document_id}: {deleted}")
        except Exception as e:
            logger.warning(f"Failed to clean up existing index for {document_id}: {e}")
        
        # Track last saved progress to avoid too many DB writes
        last_saved_progress = {"current": -1}
        
        def _update_progress_in_db(current: int, total: int) -> None:
            """Update progress in database - runs in separate thread."""
            try:
                from uu_backend.django_data.models import DocumentModel
                DocumentModel.objects.filter(id=document_id).update(
                    retrieval_index_progress=current,
                    retrieval_index_total=total
                )
            except Exception as e:
                logger.warning(f"Failed to update progress in thread: {e}")
        
        def progress_callback(stage: str, current: int, total: int) -> None:
            logger.info(f"Indexing {document_id}: {stage} {current}/{total}")
            # Update progress in database - only save periodically to reduce DB load
            if current == total or current - last_saved_progress["current"] >= max(1, total // 10):
                try:
                    import threading
                    thread = threading.Thread(target=_update_progress_in_db, args=(current, total))
                    thread.start()
                    # Don't wait for it - fire and forget
                    last_saved_progress["current"] = current
                except Exception as e:
                    logger.warning(f"Failed to start progress update thread: {e}")
        
        chunks_indexed = service.index_document(
            document_id=document_id,
            content=content,
            metadata={
                "filename": document.filename,
                "file_type": document.file_type,
            },
            progress_callback=progress_callback,
        )
        
        # Update status to completed
        doc_model.retrieval_index_status = "completed"
        doc_model.retrieval_chunks_count = chunks_indexed
        doc_model.save()
        
        logger.info(
            f"Contextual retrieval indexing complete for {document_id}: "
            f"{chunks_indexed} chunks indexed"
        )
        
        return {
            "status": "completed",
            "document_id": document_id,
            "chunks_indexed": chunks_indexed,
        }
        
    except Exception as e:
        logger.error(f"Contextual retrieval indexing failed for {document_id}: {e}")
        import traceback
        traceback.print_exc()
        
        # Update status to failed
        try:
            doc_model = DocumentModel.objects.get(id=document_id)
            doc_model.retrieval_index_status = "failed"
            doc_model.save()
        except Exception:
            pass
        
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2)
def delete_document_from_retrieval_index(self, document_id: str):
    """
    Delete a document from the contextual retrieval index.
    
    Args:
        document_id: Document ID to delete
    """
    from uu_backend.django_data.models import DocumentModel
    
    try:
        logger.info(f"Deleting document {document_id} from retrieval index")
        
        service = get_contextual_retrieval_service()
        result = service.delete_document(document_id)
        
        # Reset retrieval status
        try:
            doc_model = DocumentModel.objects.get(id=document_id)
            doc_model.retrieval_index_status = "pending"
            doc_model.retrieval_chunks_count = None
            doc_model.save()
        except DocumentModel.DoesNotExist:
            pass
        
        logger.info(f"Deleted document {document_id}: {result}")
        
        return {
            "status": "completed",
            "document_id": document_id,
            **result,
        }
        
    except Exception as e:
        logger.error(f"Failed to delete document {document_id} from index: {e}")
        raise self.retry(exc=e, countdown=30)


@shared_task
def reindex_all_documents():
    """
    Reindex all documents for contextual retrieval.
    
    This clears the existing index and reindexes all documents.
    Use with caution - this can be expensive for large document sets.
    """
    logger.info("Starting full reindex of all documents")
    
    service = get_contextual_retrieval_service()
    service.vector_store.clear()
    service.bm25_index.clear()
    
    doc_repo = get_document_repository()
    documents = doc_repo.get_all_documents()
    
    total = len(documents)
    indexed = 0
    failed = 0
    
    for i, document in enumerate(documents):
        logger.info(f"Reindexing document {i+1}/{total}: {document.id}")
        
        try:
            index_document_for_retrieval.delay(document.id)
            indexed += 1
        except Exception as e:
            logger.error(f"Failed to queue document {document.id}: {e}")
            failed += 1
    
    logger.info(f"Reindex queued: {indexed} documents, {failed} failed")
    
    return {
        "status": "completed",
        "total": total,
        "queued": indexed,
        "failed": failed,
    }
