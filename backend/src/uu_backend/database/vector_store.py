"""ChromaDB vector store for document storage and retrieval."""

from collections import defaultdict
from datetime import date, datetime

import chromadb
import tiktoken
from chromadb.config import Settings as ChromaSettings

from uu_backend.config import get_settings
from uu_backend.models.document import Document, DocumentChunk, DocumentMetadata, DocumentSummary
from uu_backend.models.timeline import (
    DateRange,
    TimelineDocument,
    TimelineEntry,
    TimelineResponse,
)


class VectorStore:
    """ChromaDB-based vector store for documents."""

    def __init__(self):
        """Initialize the vector store."""
        settings = get_settings()

        # Initialize ChromaDB with persistent storage
        self._client = chromadb.PersistentClient(
            path=str(settings.chroma_path),
            settings=ChromaSettings(anonymized_telemetry=False),
        )

        # Get or create the documents collection
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"description": "Unstructured Unlocked document chunks"},
        )

        # Separate collection for document metadata
        self._docs_collection = self._client.get_or_create_collection(
            name=f"{settings.chroma_collection_name}_metadata",
            metadata={"description": "Document metadata"},
        )
        self._token_encoding = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self._token_encoding.encode(text))

    def add_document(self, document: Document) -> None:
        """
        Add a document and its chunks to the store.

        Args:
            document: The document to add
        """
        # Store document metadata
        doc_metadata = {
            "filename": document.filename,
            "file_type": document.file_type,
            "created_at": document.created_at.isoformat(),
            "chunk_count": len(document.chunks),
            "token_count": self._count_tokens(document.content or ""),
        }

        if document.date_extracted:
            doc_metadata["date_extracted"] = document.date_extracted.isoformat()

        self._docs_collection.upsert(
            ids=[document.id],
            documents=[document.content[:1000]],  # Store excerpt
            metadatas=[doc_metadata],
        )

        # Store chunks with embeddings
        if document.chunks:
            chunk_ids = [chunk.id for chunk in document.chunks]
            chunk_texts = [chunk.content for chunk in document.chunks]
            chunk_metadatas = [
                {
                    "document_id": document.id,
                    "filename": document.filename,
                    "chunk_index": chunk.chunk_index,
                    "date_extracted": (
                        document.date_extracted.isoformat()
                        if document.date_extracted
                        else ""
                    ),
                }
                for chunk in document.chunks
            ]

            self._collection.upsert(
                ids=chunk_ids,
                documents=chunk_texts,
                metadatas=chunk_metadatas,
            )

    def update_document_content(self, document_id: str, new_content: str) -> bool:
        """
        Update document content after reprocessing.
        
        Args:
            document_id: Document ID
            new_content: New content from reprocessing
            
        Returns:
            True if successful
        """
        from uu_backend.ingestion.chunker import get_chunker
        
        # Get existing document
        document = self.get_document(document_id)
        if not document:
            return False
        
        # Delete old chunks
        self._collection.delete(where={"document_id": document_id})
        
        # Create new chunks
        chunker = get_chunker()
        new_chunks = chunker.chunk(new_content, document_id)
        
        # Update document metadata with new content
        doc_metadata = {
            "filename": document.filename,
            "file_type": document.file_type,
            "created_at": document.created_at.isoformat(),
            "chunk_count": len(new_chunks),
            "token_count": self._count_tokens(new_content),
        }
        
        if document.date_extracted:
            doc_metadata["date_extracted"] = document.date_extracted.isoformat()
        
        self._docs_collection.upsert(
            ids=[document_id],
            documents=[new_content[:1000]],
            metadatas=[doc_metadata],
        )
        
        # Add new chunks
        if new_chunks:
            chunk_ids = [chunk.id for chunk in new_chunks]
            chunk_texts = [chunk.content for chunk in new_chunks]
            chunk_metadatas = [
                {
                    "document_id": document_id,
                    "filename": document.filename,
                    "chunk_index": chunk.chunk_index,
                    "date_extracted": (
                        document.date_extracted.isoformat()
                        if document.date_extracted
                        else ""
                    ),
                }
                for chunk in new_chunks
            ]
            
            self._collection.upsert(
                ids=chunk_ids,
                documents=chunk_texts,
                metadatas=chunk_metadatas,
            )
        
        return True

    def get_document(self, document_id: str) -> Document | None:
        """
        Retrieve a document by ID.

        Args:
            document_id: The document ID

        Returns:
            The document or None if not found
        """
        # Get document metadata
        result = self._docs_collection.get(
            ids=[document_id],
            include=["documents", "metadatas"],
        )

        if not result["ids"]:
            return None

        metadata = result["metadatas"][0]
        content = result["documents"][0]

        # Get associated chunks
        chunks_result = self._collection.get(
            where={"document_id": document_id},
            include=["documents", "metadatas"],
        )

        chunks = [
            DocumentChunk(
                id=chunk_id,
                document_id=document_id,
                content=chunk_content,
                chunk_index=chunk_meta.get("chunk_index", 0),
                metadata=chunk_meta,
            )
            for chunk_id, chunk_content, chunk_meta in zip(
                chunks_result["ids"],
                chunks_result["documents"],
                chunks_result["metadatas"],
            )
        ]

        # Sort chunks by index
        chunks.sort(key=lambda c: c.chunk_index)

        # Reconstruct full content from chunks if available
        if chunks:
            full_content = "\n\n".join(c.content for c in chunks)
        else:
            full_content = content

        # Parse date
        date_extracted = None
        if metadata.get("date_extracted"):
            try:
                date_extracted = datetime.fromisoformat(metadata["date_extracted"])
            except ValueError:
                pass

        return Document(
            id=document_id,
            filename=metadata["filename"],
            file_type=metadata["file_type"],
            content=full_content,
            date_extracted=date_extracted,
            created_at=datetime.fromisoformat(metadata["created_at"]),
            metadata=DocumentMetadata(
                filename=metadata["filename"],
                file_type=metadata["file_type"],
                date_extracted=date_extracted,
            ),
            chunks=chunks,
        )

    def get_all_documents(self) -> list[DocumentSummary]:
        """
        Get all documents as summaries.

        Returns:
            List of document summaries
        """
        result = self._docs_collection.get(include=["documents", "metadatas"])

        summaries = []
        for doc_id, content, metadata in zip(
            result["ids"], result["documents"], result["metadatas"]
        ):
            date_extracted = None
            if metadata.get("date_extracted"):
                try:
                    date_extracted = datetime.fromisoformat(metadata["date_extracted"])
                except ValueError:
                    pass
            token_count = metadata.get("token_count")
            if token_count is None:
                # Backfill for older records that predate token_count metadata
                token_count = self._count_tokens(content or "")
                metadata["token_count"] = token_count
                self._docs_collection.upsert(
                    ids=[doc_id],
                    documents=[content or ""],
                    metadatas=[metadata],
                )

            summaries.append(
                DocumentSummary(
                    id=doc_id,
                    filename=metadata["filename"],
                    file_type=metadata["file_type"],
                    date_extracted=date_extracted,
                    created_at=datetime.fromisoformat(metadata["created_at"]),
                    chunk_count=metadata.get("chunk_count", 0),
                    token_count=int(token_count or 0),
                )
            )

        return summaries

    def get_timeline(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TimelineResponse:
        """
        Get documents grouped by date for timeline visualization.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            TimelineResponse with grouped documents
        """
        # Get all documents with dates
        result = self._docs_collection.get(include=["documents", "metadatas"])

        # Group by date
        by_date: dict[date, list[TimelineDocument]] = defaultdict(list)
        earliest: date | None = None
        latest: date | None = None
        total = 0

        for doc_id, excerpt, metadata in zip(
            result["ids"], result["documents"], result["metadatas"]
        ):
            date_str = metadata.get("date_extracted")
            if not date_str:
                continue

            try:
                doc_date = datetime.fromisoformat(date_str).date()
            except ValueError:
                continue

            # Apply date filters
            if start_date and doc_date < start_date:
                continue
            if end_date and doc_date > end_date:
                continue

            # Track range
            if earliest is None or doc_date < earliest:
                earliest = doc_date
            if latest is None or doc_date > latest:
                latest = doc_date

            total += 1

            by_date[doc_date].append(
                TimelineDocument(
                    id=doc_id,
                    filename=metadata["filename"],
                    file_type=metadata["file_type"],
                    title=metadata["filename"],
                    excerpt=excerpt[:200] if excerpt else None,
                )
            )

        # Convert to timeline entries
        timeline = [
            TimelineEntry(
                date=d,
                document_count=len(docs),
                documents=docs,
            )
            for d, docs in sorted(by_date.items())
        ]

        return TimelineResponse(
            timeline=timeline,
            date_range=DateRange(earliest=earliest, latest=latest),
            total_documents=total,
        )

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and its chunks.

        Args:
            document_id: The document ID to delete

        Returns:
            True if deleted, False if not found
        """
        # Check if exists
        result = self._docs_collection.get(ids=[document_id])
        if not result["ids"]:
            return False

        # Delete chunks
        chunks = self._collection.get(where={"document_id": document_id})
        if chunks["ids"]:
            self._collection.delete(ids=chunks["ids"])

        # Delete document
        self._docs_collection.delete(ids=[document_id])

        return True

    def get_document_id_for_chunk(self, chunk_id: str) -> str | None:
        """
        Resolve a document ID from a chunk ID.

        Args:
            chunk_id: Chunk ID in the chunk collection

        Returns:
            Document ID if found, otherwise None
        """
        try:
            result = self._collection.get(
                ids=[chunk_id],
                include=["metadatas"],
            )
        except Exception:
            return None

        if not result.get("ids"):
            return None

        metadatas = result.get("metadatas") or []
        if not metadatas:
            return None

        metadata = metadatas[0] or {}
        document_id = metadata.get("document_id")
        return str(document_id) if document_id else None

    def count(self) -> int:
        """Get the total number of documents."""
        return self._docs_collection.count()

    def chunk_count(self) -> int:
        """Get the total number of chunks."""
        return self._collection.count()

    def semantic_search(
        self, 
        query: str, 
        n_results: int = 5,
        document_ids: list[str] | None = None
    ) -> list[dict]:
        """
        Search for documents using semantic similarity.
        
        Args:
            query: The search query
            n_results: Maximum number of results to return
            document_ids: Optional list of document IDs to search within
            
        Returns:
            List of search results with document info and relevance scores
        """
        if document_ids is not None and len(document_ids) == 0:
            return []

        where_filter = None
        if document_ids is not None:
            where_filter = {"document_id": {"$in": document_ids}}
        
        results = self._collection.query(
            query_texts=[query],
            n_results=n_results,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        
        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, chunk_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                content = results["documents"][0][i] if results["documents"] else ""
                distance = results["distances"][0][i] if results["distances"] else 0
                
                # Convert distance to similarity score (ChromaDB uses L2 distance)
                similarity = 1.0 / (1.0 + distance)
                
                search_results.append({
                    "chunk_id": chunk_id,
                    "document_id": metadata.get("document_id"),
                    "filename": metadata.get("filename"),
                    "chunk_index": metadata.get("chunk_index", 0),
                    "content": content,
                    "similarity": similarity,
                })
        
        return search_results


# Module-level instance
_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get or create the VectorStore instance."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
