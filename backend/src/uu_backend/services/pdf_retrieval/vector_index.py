"""Persistent Qdrant vector index for PDF retrieval."""

from __future__ import annotations

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from uu_backend.config import get_settings
from uu_backend.django_data import models as orm
from uu_backend.services.contextual_retrieval.models import SearchResult


class PDFVectorIndex:
    COLLECTION_PREFIX = "pdf_doc_"

    def __init__(self):
        settings = get_settings()
        if settings.qdrant_url:
            self.client = QdrantClient(url=settings.qdrant_url)
        else:
            self.client = QdrantClient(path=str(settings.qdrant_pdf_storage_path))

    def _collection_name(self, document_id: str) -> str:
        return f"{self.COLLECTION_PREFIX}{document_id.replace('-', '_')}"

    def _ensure_collection(self, document_id: str, vector_size: int) -> str:
        collection_name = self._collection_name(document_id)
        try:
            info = self.client.get_collection(collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=qmodels.VectorParams(
                    size=vector_size,
                    distance=qmodels.Distance.COSINE,
                ),
            )
            return collection_name

        size = getattr(info.config.params.vectors, "size", None)
        if size is not None and int(size) != vector_size:
            raise ValueError(
                f"Qdrant vector size changed for {document_id}: {size} -> {vector_size}"
            )
        return collection_name

    def upsert_document(
        self,
        document_id: str,
        chunks: list[orm.RetrievalChunkModel],
        embeddings: list[list[float]],
    ) -> None:
        """Upsert chunk embeddings into the per-document Qdrant collection."""
        if not chunks or not embeddings:
            return
        collection_name = self._ensure_collection(document_id, len(embeddings[0]))
        points = []
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            asset = chunk.asset
            citation = getattr(chunk, "citation", None)
            points.append(
                qmodels.PointStruct(
                    id=chunk.id,
                    vector=embedding,
                    payload={
                        "document_id": document_id,
                        "chunk_id": chunk.id,
                        "chunk_index": chunk.chunk_index,
                        "chunk_type": chunk.chunk_type,
                        "page_id": chunk.page_id,
                        "page_number": chunk.page.page_number,
                        "asset_id": asset.id if asset else None,
                        "asset_type": asset.asset_type if asset else None,
                        "asset_label": asset.label if asset else None,
                        "preview_artifact_id": (citation.preview_artifact_id if citation else None),
                        "citation_id": citation.id if citation else None,
                        "citation_regions": citation.regions if citation else [],
                        "content": chunk.content,
                        "original_text": (asset.text_content if asset else chunk.content),
                        "context": (
                            asset.metadata.get("summary", "")
                            if asset and isinstance(asset.metadata, dict)
                            else ""
                        ),
                        "metadata": chunk.metadata or {},
                    },
                )
            )
        self.client.upsert(collection_name=collection_name, points=points)

    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: int,
        filter_doc_id: str | None = None,
        asset_types: set[str] | None = None,
    ) -> list[SearchResult]:
        """Query Qdrant for the top-k most similar chunks across one or all documents."""
        document_ids: list[str]
        if filter_doc_id:
            document_ids = [filter_doc_id]
        else:
            document_ids = list(
                orm.DocumentModel.objects.filter(
                    retrieval_index_status="completed",
                    retrieval_index_backend="intelligent_pdf_v1",
                ).values_list("id", flat=True)
            )

        all_results: list[SearchResult] = []
        for document_id in document_ids:
            collection_name = self._collection_name(document_id)
            try:
                response = self.client.query_points(
                    collection_name=collection_name,
                    query=query_embedding,
                    limit=top_k * 3,
                    with_payload=True,
                )
            except Exception:  # nosec B112
                continue

            for point in response.points:
                payload = point.payload or {}
                asset_type = payload.get("asset_type")
                if asset_types and asset_type not in asset_types:
                    continue
                metadata = payload.get("metadata", {}) or {}
                metadata = dict(metadata)
                metadata.setdefault("page_number", payload.get("page_number"))
                metadata.setdefault("asset_type", asset_type)
                metadata.setdefault("asset_label", payload.get("asset_label"))
                metadata.setdefault("citation_id", payload.get("citation_id"))
                metadata.setdefault("citation_regions", payload.get("citation_regions", []))
                metadata.setdefault("preview_artifact_id", payload.get("preview_artifact_id"))
                all_results.append(
                    SearchResult(
                        doc_id=str(payload.get("document_id", document_id)),
                        chunk_index=int(payload.get("chunk_index", 0) or 0),
                        text=str(payload.get("content", "")),
                        original_text=str(payload.get("original_text", "")),
                        context=str(payload.get("context", "")),
                        score=float(point.score or 0.0),
                        metadata=metadata,
                        chunk_id=str(payload.get("chunk_id", "") or ""),
                        page_number=(
                            int(payload.get("page_number"))
                            if payload.get("page_number") is not None
                            else None
                        ),
                        asset_type=str(asset_type) if asset_type else None,
                        asset_label=(
                            str(payload.get("asset_label"))
                            if payload.get("asset_label") is not None
                            else None
                        ),
                        citation_id=(
                            str(payload.get("citation_id"))
                            if payload.get("citation_id") is not None
                            else None
                        ),
                        citation_regions=list(payload.get("citation_regions", []) or []),
                        preview_artifact_id=(
                            str(payload.get("preview_artifact_id"))
                            if payload.get("preview_artifact_id") is not None
                            else None
                        ),
                    )
                )

        all_results.sort(key=lambda result: result.score, reverse=True)
        return all_results[:top_k]

    def delete_document(self, document_id: str) -> int:
        """Delete the Qdrant collection for a document and return the number of points removed."""
        collection_name = self._collection_name(document_id)
        try:
            collection = self.client.get_collection(collection_name)
            points_count = int(collection.points_count or 0)
        except Exception:
            points_count = 0
        try:
            self.client.delete_collection(collection_name)
        except Exception:
            return points_count
        return points_count

    def count(self) -> int:
        """Return the total number of indexed vector points across all PDF documents."""
        total = 0
        for document_id in orm.DocumentModel.objects.filter(
            retrieval_index_status="completed",
            retrieval_index_backend="intelligent_pdf_v1",
        ).values_list("id", flat=True):
            try:
                info = self.client.get_collection(self._collection_name(str(document_id)))
                total += int(info.points_count or 0)
            except Exception:  # nosec B112
                continue
        return total
