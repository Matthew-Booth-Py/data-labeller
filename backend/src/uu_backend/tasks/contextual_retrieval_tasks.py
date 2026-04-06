"""Celery tasks for Contextual Retrieval indexing."""

import logging
from pathlib import Path

from celery import shared_task

from uu_backend.config import get_settings
from uu_backend.ingestion.converter import extract_pdf_with_tables, postprocess_markdown
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.contextual_retrieval import get_contextual_retrieval_service
from uu_backend.services.pdf_retrieval import PDF_RETRIEVAL_BACKEND

logger = logging.getLogger(__name__)


def _resolve_document_file_path(document) -> Path | None:
    if document.file_path:
        file_path = Path(document.file_path)
        if file_path.exists():
            return file_path

    if not document.file_type:
        return None

    settings = get_settings()
    candidate = settings.file_storage_path / f"{document.id}.{document.file_type.lower()}"
    return candidate if candidate.exists() else None


def _load_document_content_for_retrieval(document) -> str:
    file_type = (document.file_type or "").lower()
    if file_type == "pdf":
        file_path = _resolve_document_file_path(document)
        if file_path:
            content, _ = extract_pdf_with_tables(str(file_path))
            content = postprocess_markdown(content)
            if content.strip():
                return content
    return document.content or ""


@shared_task(bind=True, max_retries=3)
def index_document_for_retrieval(self, document_id: str):
    """Index a document for contextual retrieval.

    Builds the PDF-only intelligent retrieval index.

    Parameters
    ----------
    document_id : str
        Document ID to index.
    """
    from uu_backend.django_data.models import DocumentModel

    try:
        logger.info(f"Starting contextual retrieval indexing for document {document_id}")

        doc_model = DocumentModel.objects.get(id=document_id)
        doc_model.retrieval_index_status = "processing"
        doc_model.retrieval_index_progress = 0
        doc_model.retrieval_index_total = None
        doc_model.retrieval_index_backend = None
        doc_model.save()

        doc_repo = get_document_repository()
        document = doc_repo.get_document(document_id)

        if not document:
            logger.error(f"Document {document_id} not found")
            doc_model.retrieval_index_status = "failed"
            doc_model.save()
            return {"status": "error", "message": "Document not found"}

        if (document.file_type or "").lower() != "pdf":
            message = "PDF-only retrieval is supported. Reindexing requires a PDF document."
            logger.warning("%s: %s", document_id, message)
            doc_model.retrieval_index_status = "failed"
            doc_model.retrieval_index_backend = None
            doc_model.save(update_fields=["retrieval_index_status", "retrieval_index_backend"])
            return {"status": "error", "message": message}

        file_path = _resolve_document_file_path(document)
        if not file_path:
            message = "Stored PDF file could not be resolved for retrieval indexing."
            logger.warning("%s: %s", document_id, message)
            doc_model.retrieval_index_status = "failed"
            doc_model.retrieval_index_backend = None
            doc_model.save(update_fields=["retrieval_index_status", "retrieval_index_backend"])
            return {"status": "error", "message": message}

        service = get_contextual_retrieval_service()

        try:
            deleted = service.delete_document(document_id)
            if deleted.get("vector_store", 0) > 0 or deleted.get("artifacts", 0) > 0:
                logger.info(f"Cleaned up existing index for {document_id}: {deleted}")
        except Exception as e:
            logger.warning(f"Failed to clean up existing index for {document_id}: {e}")

        last_saved_progress = {"current": -1}

        def _update_progress_in_db(current: int, total: int) -> None:
            try:
                from uu_backend.django_data.models import DocumentModel

                DocumentModel.objects.filter(id=document_id).update(
                    retrieval_index_progress=current, retrieval_index_total=total
                )
            except Exception as e:
                logger.warning(f"Failed to update progress in thread: {e}")

        def progress_callback(stage: str, current: int, total: int) -> None:
            """Log indexing progress and persist it to the database periodically."""
            logger.info(f"Indexing {document_id}: {stage} {current}/{total}")
            if current == total or current - last_saved_progress["current"] >= max(1, total // 10):
                try:
                    import threading

                    thread = threading.Thread(target=_update_progress_in_db, args=(current, total))
                    thread.start()
                    last_saved_progress["current"] = current
                except Exception as e:
                    logger.warning(f"Failed to start progress update thread: {e}")

        chunks_indexed = service.index_document(
            document_id=document_id,
            content=None,
            metadata=None,
            progress_callback=progress_callback,
        )

        doc_model.retrieval_index_status = "completed"
        doc_model.retrieval_chunks_count = chunks_indexed
        doc_model.retrieval_index_backend = PDF_RETRIEVAL_BACKEND
        doc_model.save(
            update_fields=[
                "retrieval_index_status",
                "retrieval_chunks_count",
                "retrieval_index_backend",
            ]
        )

        logger.info(
            f"Contextual retrieval indexing complete for {document_id}: "
            f"{chunks_indexed} chunks indexed"
        )

        return {
            "status": "completed",
            "document_id": document_id,
            "chunks_indexed": chunks_indexed,
            "retrieval_index_backend": PDF_RETRIEVAL_BACKEND,
        }

    except Exception as e:
        logger.error(f"Contextual retrieval indexing failed for {document_id}: {e}")
        import traceback

        traceback.print_exc()

        # Update status to failed
        try:
            doc_model = DocumentModel.objects.get(id=document_id)
            doc_model.retrieval_index_status = "failed"
            doc_model.retrieval_index_backend = None
            doc_model.save(update_fields=["retrieval_index_status", "retrieval_index_backend"])
        except Exception:  # nosec B110
            pass

        raise self.retry(exc=e, countdown=60)
