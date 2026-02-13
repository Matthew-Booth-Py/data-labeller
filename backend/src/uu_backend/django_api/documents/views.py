"""DRF views for documents endpoints."""

import logging
from pathlib import Path

from django.http import FileResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.config import get_settings
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.ingestion.converter import get_converter
from uu_backend.models.document import DocumentListResponse, DocumentResponse
from uu_backend.repositories import get_repository

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
        store = get_document_repository()
        document = document_repo.get_document(document_id)
        if not document:
            return Response({"detail": f"Document not found: {document_id}"}, status=404)

        payload = DocumentResponse(document=document)
        return Response(payload.model_dump(mode="json"))

    # Individual document deletion disabled - use bulk operations instead
    # def delete(self, request, document_id: str):
    #     store = get_document_repository()
    #     neo4j_client = get_neo4j_client()
    #     document = document_repo.get_document(document_id)
    #
    #     if document:
    #         file_path = get_original_file_path(document_id, document.file_type)
    #         if file_path:
    #             file_path.unlink(missing_ok=True)
    #
    #     deleted = document_repo.delete_document(document_id)
    #     if not deleted:
    #         return Response({"detail": f"Document not found: {document_id}"}, status=404)
    #
    #     graph_cleanup: dict[str, object]
    #     try:
    #         graph_cleanup = neo4j_client.delete_document_graph_data(document_id)
    #         valid_doc_ids = [doc.id for doc in document_repo.get_all_documents()]
    #         graph_cleanup["reconcile"] = neo4j_client.reconcile_documents(valid_doc_ids)
    #     except Exception as exc:
    #         logger.exception("graph_document_delete_failed", extra={"document_id": document_id})
    #         graph_cleanup = {"error": str(exc)}
    #
    #     return Response(
    #         {
    #             "status": "deleted",
    #             "document_id": document_id,
    #             "graph_cleanup": graph_cleanup,
    #         }
    #     )


class DocumentFileView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, document_id: str):
        store = get_document_repository()
        document = document_repo.get_document(document_id)
        if not document:
            return Response({"detail": f"Document not found: {document_id}"}, status=404)

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


class DocumentReprocessView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request, document_id: str):
        store = get_document_repository()
        document = document_repo.get_document(document_id)

        if not document:
            return Response({"detail": "Document not found"}, status=404)

        file_path = get_original_file_path(document_id, document.file_type)
        if not file_path:
            return Response({"detail": "Original file not found"}, status=404)

        try:
            converter = get_converter()
            with open(file_path, "rb") as file_obj:
                result = converter.convert(file_obj, document.filename)

            if not result.success:
                return Response({"detail": f"Conversion failed: {result.error}"}, status=500)

            document_repo.update_document_content(document_id, result.content)
            return Response(
                {
                    "status": "reprocessed",
                    "document_id": document_id,
                    "content_length": len(result.content),
                    "message": "Document reprocessed successfully. Note: Existing annotations may have invalid offsets.",
                }
            )
        except Exception as exc:
            return Response({"detail": f"Reprocessing failed: {exc}"}, status=500)
