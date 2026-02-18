"""Celery tasks for Azure Document Intelligence processing."""

import logging
from pathlib import Path

from celery import shared_task

from uu_backend.config import get_settings
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.azure_di_service import get_azure_di_service

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def analyze_document_with_azure_di(self, document_id: str, file_path: str):
    """
    Analyze a document with Azure Document Intelligence and cache the results.
    
    Args:
        document_id: Document ID
        file_path: Path to the document file
    """
    try:
        logger.info(f"Starting Azure DI analysis for document {document_id}")
        print(f"=== Azure DI Analysis Task Started for {document_id} ===")
        
        # Update status to processing
        doc_repo = get_document_repository()
        document = doc_repo.get_document(document_id)
        
        if not document:
            logger.error(f"Document {document_id} not found")
            return {"status": "error", "message": "Document not found"}
        
        # Update status
        from uu_backend.django_data.models import DocumentModel
        doc_model = DocumentModel.objects.get(id=document_id)
        doc_model.azure_di_status = "processing"
        doc_model.save()
        
        # Analyze document
        azure_di = get_azure_di_service()
        file_path_obj = Path(file_path)
        
        if not file_path_obj.exists():
            logger.error(f"File not found: {file_path}")
            doc_model.azure_di_status = "failed"
            doc_model.save()
            return {"status": "error", "message": "File not found"}
        
        # Run analysis (this is synchronous in Celery context)
        import asyncio
        analysis = asyncio.run(azure_di.analyze_document(file_path_obj))
        
        logger.info(f"Azure DI analysis complete for {document_id}: {len(analysis['pages'])} pages")
        print(f"Analysis complete: {len(analysis['pages'])} pages, {len(analysis.get('content', ''))} chars")
        
        # Cache the results
        doc_model.azure_di_analysis = analysis
        doc_model.azure_di_status = "completed"
        doc_model.save()
        
        logger.info(f"Azure DI analysis cached for document {document_id}")
        
        return {
            "status": "completed",
            "pages": len(analysis['pages']),
            "content_length": len(analysis.get('content', ''))
        }
        
    except Exception as e:
        logger.error(f"Azure DI analysis failed for {document_id}: {e}")
        print(f"!!! Azure DI Analysis Failed: {e}")
        import traceback
        traceback.print_exc()
        
        # Update status to failed
        try:
            from uu_backend.django_data.models import DocumentModel
            doc_model = DocumentModel.objects.get(id=document_id)
            doc_model.azure_di_status = "failed"
            doc_model.save()
        except Exception:
            pass
        
        # Retry on failure
        raise self.retry(exc=e, countdown=60)
