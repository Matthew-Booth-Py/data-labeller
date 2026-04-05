"""DRF views for documents endpoints."""

import logging
from pathlib import Path

from django.http import FileResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.config import get_settings
from uu_backend.models.document import DocumentListResponse, DocumentResponse
from uu_backend.repositories import get_repository
from uu_backend.repositories.document_repository import get_document_repository

logger = logging.getLogger(__name__)


def get_original_file_path(document_id: str, file_type: str) -> Path | None:
    """Find the original file for a document."""
    settings = get_settings()
    storage_path = settings.file_storage_path

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

    for extension in ext_map.values():
        alt_path = storage_path / f"{document_id}{extension}"
        if alt_path.exists():
            return alt_path

    return None


class DocumentsListView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        document_repo = get_document_repository()
        repository = get_repository()
        documents = document_repo.get_all_documents()

        for doc in documents:
            classification = repository.get_classification(doc.id)
            if classification:
                doc_type = repository.get_document_type(classification.document_type_id)
                if doc_type:
                    doc.document_type = doc_type

        payload = DocumentListResponse(documents=documents, total=len(documents))
        return Response(payload.model_dump(mode="json"))


class DocumentDetailView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, document_id: str):
        document_repo = get_document_repository()
        document = document_repo.get_document(document_id)
        if not document:
            return Response({"detail": f"Document not found: {document_id}"}, status=404)

        payload = DocumentResponse(document=document)
        return Response(payload.model_dump(mode="json"))

    def delete(self, request, document_id: str):
        """Delete a document by ID."""
        document_repo = get_document_repository()
        document = document_repo.get_document(document_id)

        if document:
            try:
                from uu_backend.services.contextual_retrieval import (
                    get_contextual_retrieval_service,
                )

                get_contextual_retrieval_service().delete_document(document_id)
            except Exception as exc:
                logger.warning("Failed to delete retrieval artifacts for %s: %s", document_id, exc)

            # Delete the file from storage if it exists
            file_path = get_original_file_path(document_id, document.file_type)
            if file_path:
                file_path.unlink(missing_ok=True)

        deleted = document_repo.delete_document(document_id)
        if not deleted:
            return Response({"detail": f"Document not found: {document_id}"}, status=404)

        return Response(
            {
                "status": "deleted",
                "document_id": document_id,
            }
        )


class DocumentFileView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, document_id: str):
        document_repo = get_document_repository()
        document = document_repo.get_document(document_id)
        if not document:
            return Response({"detail": f"Document not found: {document_id}"}, status=404)

        # Always serve original file
        file_path = get_original_file_path(document_id, document.file_type)
        if not file_path:
            return Response(
                {"detail": f"Original file not found for document: {document_id}"},
                status=404,
            )

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

        download = str(request.query_params.get("download", "false")).lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        content_disposition = (
            f'attachment; filename="{document.filename}"'
            if download
            else f'inline; filename="{document.filename}"'
        )

        response = FileResponse(
            open(file_path, "rb"),
            content_type=media_types.get(file_path.suffix.lower(), "application/octet-stream"),
        )
        response["Content-Disposition"] = content_disposition
        return response


class DocumentReindexRetrievalView(APIView):
    """Trigger contextual retrieval reindexing for a document."""

    def post(self, request, document_id: str):
        """Queue contextual retrieval indexing for a document."""
        from uu_backend.services.contextual_retrieval import get_contextual_retrieval_service
        from uu_backend.tasks.contextual_retrieval_tasks import index_document_for_retrieval

        document_repo = get_document_repository()
        document = document_repo.get_document(document_id)

        if not document:
            return Response({"detail": "Document not found"}, status=404)

        # Delete existing index for this document
        try:
            service = get_contextual_retrieval_service()
            service.delete_document(document_id)
        except Exception as e:
            logger.warning(f"Failed to delete existing index for {document_id}: {e}")

        # Reset status
        from uu_backend.django_data.models import DocumentModel

        doc_model = DocumentModel.objects.get(id=document_id)
        doc_model.retrieval_index_status = "pending"
        doc_model.retrieval_chunks_count = None
        doc_model.retrieval_index_progress = 0
        doc_model.retrieval_index_total = None
        doc_model.retrieval_index_backend = None
        doc_model.save(
            update_fields=[
                "retrieval_index_status",
                "retrieval_chunks_count",
                "retrieval_index_progress",
                "retrieval_index_total",
                "retrieval_index_backend",
            ]
        )

        # Queue indexing
        try:
            index_document_for_retrieval.delay(document_id)
            logger.info(f"Queued retrieval reindexing for document {document_id}")

            return Response(
                {
                    "status": "queued",
                    "document_id": document_id,
                    "message": "Retrieval indexing queued successfully",
                }
            )
        except Exception as e:
            logger.error(f"Failed to queue retrieval indexing: {e}")
            return Response({"detail": f"Failed to queue indexing: {str(e)}"}, status=500)
