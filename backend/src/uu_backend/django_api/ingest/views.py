"""DRF views for ingest endpoints."""

import logging
import time
import uuid
from pathlib import Path

from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.config import get_settings
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.ingestion.converter import get_converter
from uu_backend.ingestion.dates import extract_date
from uu_backend.models.document import Document, IngestResponse
from uu_backend.tasks.azure_di_tasks import analyze_document_with_azure_di

logger = logging.getLogger(__name__)


class IngestView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        files = request.FILES.getlist("files")
        if not files:
            return Response({"detail": "files is required"}, status=422)

        start_time = time.time()
        settings = get_settings()

        converter = get_converter()
        document_repo = get_document_repository()

        documents_processed = 0
        document_ids: list[str] = []
        errors: list[str] = []

        for upload_file in files:
            filename = upload_file.name or "unknown"
            if not converter.is_supported(filename):
                errors.append(f"{filename}: Unsupported file type")
                continue

            try:
                doc_id = str(uuid.uuid4())
                file_ext = Path(filename).suffix.lower()
                original_file_path = settings.file_storage_path / f"{doc_id}{file_ext}"

                with open(original_file_path, "wb") as file_obj:
                    file_obj.write(upload_file.read())
                upload_file.seek(0)

                result = converter.convert(upload_file.file, filename)
                if not result.success:
                    errors.append(f"{filename}: {result.error}")
                    original_file_path.unlink(missing_ok=True)
                    continue

                date_extracted = extract_date(result.content)
                result.metadata.date_extracted = date_extracted

                document = Document(
                    id=doc_id,
                    filename=filename,
                    file_type=result.metadata.file_type,
                    content=result.content,
                    date_extracted=date_extracted,
                    metadata=result.metadata,
                    file_path=str(original_file_path),
                )

                # Store document in database
                try:
                    document_repo.add_document(document)
                except Exception as store_error:
                    original_file_path.unlink(missing_ok=True)
                    errors.append(
                        f"{filename}: Failed to store: {store_error}"
                    )
                    continue

                # Trigger Azure DI analysis for PDF and image documents
                if file_ext.lower() in ['.pdf', '.png', '.jpg', '.jpeg', '.gif', '.webp']:
                    try:
                        analyze_document_with_azure_di.delay(doc_id, str(original_file_path))
                        logger.info(f"Queued Azure DI analysis for {filename}")
                    except Exception as azure_error:
                        logger.error(f"Failed to queue Azure DI analysis for {filename}: {azure_error}")
                        # Don't fail the upload, just log the error

                documents_processed += 1
                document_ids.append(doc_id)
            except Exception as exc:
                errors.append(f"{filename}: {exc}")
            finally:
                try:
                    upload_file.seek(0)
                except Exception:
                    pass

        processing_time = time.time() - start_time
        if documents_processed == 0 and errors:
            return Response(
                {"detail": {"message": "All documents failed to process", "errors": errors}},
                status=400,
            )

        payload = IngestResponse(
            status="success" if not errors else "partial",
            documents_processed=documents_processed,
            processing_time_seconds=round(processing_time, 2),
            document_ids=document_ids,
            errors=errors,
        )
        return Response(payload.model_dump(mode="json"))


class IngestStatusView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        document_repo = get_document_repository()

        return Response(
            {
                "documents": document_repo.count(),
            }
        )
