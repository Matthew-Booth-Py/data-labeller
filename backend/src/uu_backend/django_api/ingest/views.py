"""DRF views for ingest endpoints."""

import time
import uuid
from pathlib import Path

from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.config import get_settings
from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.ingestion.chunker import get_chunker
from uu_backend.ingestion.converter import get_converter
from uu_backend.ingestion.dates import extract_date
from uu_backend.models.document import Document, IngestResponse


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
        chunker = get_chunker()
        neo4j_client = get_neo4j_client()

        documents_processed = 0
        chunks_created = 0
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

                chunks = chunker.chunk(
                    content=result.content,
                    document_id=doc_id,
                    metadata={
                        "filename": filename,
                        "file_type": result.metadata.file_type,
                    },
                )

                document = Document(
                    id=doc_id,
                    filename=filename,
                    file_type=result.metadata.file_type,
                    content=result.content,
                    date_extracted=date_extracted,
                    metadata=result.metadata,
                    chunks=chunks,
                )

                # Store document and chunks immediately in Neo4j for visibility
                # Full GraphRAG indexing will be triggered separately via "Index DB" button
                try:
                    chunk_data = [
                        {
                            "id": chunk.id,
                            "content": chunk.content,
                            "chunk_index": chunk.chunk_index,
                        }
                        for chunk in chunks
                    ]
                    neo4j_client.create_document_with_chunks(
                        doc_id=doc_id,
                        filename=filename,
                        file_type=result.metadata.file_type,
                        content=result.content,
                        chunks=chunk_data,
                        date_extracted=date_extracted,
                    )
                except Exception as neo4j_error:
                    original_file_path.unlink(missing_ok=True)
                    errors.append(
                        f"{filename}: Failed to store in Neo4j: {neo4j_error}"
                    )
                    continue

                documents_processed += 1
                chunks_created += len(chunks)
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
            chunks_created=chunks_created,
            processing_time_seconds=round(processing_time, 2),
            document_ids=document_ids,
            errors=errors,
        )
        return Response(payload.model_dump(mode="json"))


class IngestStatusView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        vector_store = get_vector_store()
        neo4j_client = get_neo4j_client()
        try:
            graph_stats = neo4j_client.get_stats()
        except Exception:
            graph_stats = {}

        return Response(
            {
                "documents": vector_store.count(),
                "chunks": vector_store.chunk_count(),
                "graph": graph_stats,
            }
        )
