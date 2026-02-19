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
    2. Chunks the document
    3. Generates context for each chunk using LLM
    4. Generates embeddings
    5. Stores in vector DB and BM25 index
    
    Args:
        document_id: Document ID to index
    """
    try:
        logger.info(f"Starting contextual retrieval indexing for document {document_id}")
        
        doc_repo = get_document_repository()
        document = doc_repo.get_document(document_id)
        
        if not document:
            logger.error(f"Document {document_id} not found")
            return {"status": "error", "message": "Document not found"}
        
        content = document.content
        if not content or not content.strip():
            logger.warning(f"Document {document_id} has no content to index")
            return {"status": "skipped", "message": "No content to index"}
        
        service = get_contextual_retrieval_service()
        
        def progress_callback(stage: str, current: int, total: int) -> None:
            logger.info(f"Indexing {document_id}: {stage} {current}/{total}")
        
        chunks_indexed = service.index_document(
            document_id=document_id,
            content=content,
            metadata={
                "filename": document.filename,
                "file_type": document.file_type,
            },
            progress_callback=progress_callback,
        )
        
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
        
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=2)
def delete_document_from_retrieval_index(self, document_id: str):
    """
    Delete a document from the contextual retrieval index.
    
    Args:
        document_id: Document ID to delete
    """
    try:
        logger.info(f"Deleting document {document_id} from retrieval index")
        
        service = get_contextual_retrieval_service()
        result = service.delete_document(document_id)
        
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
