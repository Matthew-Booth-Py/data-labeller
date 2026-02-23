"""ChromaDB vector store for contextual retrieval."""

import os
from typing import Any

import chromadb
from chromadb.config import Settings

from .models import ContextualizedChunk, SearchResult


class ChromaVectorStore:
    """
    ChromaDB-based vector store for storing and searching embeddings.
    
    Uses one collection per document for isolation and reliability.
    Uses cosine similarity by default for semantic search.
    """

    def __init__(
        self,
        persist_directory: str | None = None,
        collection_name: str = "contextual_chunks",
    ):
        self.persist_directory = persist_directory or os.getenv(
            "CHROMA_PERSIST_DIRECTORY", "./data/chroma"
        )
        
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
    
    def _get_collection_name(self, doc_id: str) -> str:
        """Get collection name for a document."""
        return f"doc_{doc_id.replace('-', '_')}"
    
    def _get_or_create_collection(self, doc_id: str):
        """Get or create collection for a document."""
        collection_name = self._get_collection_name(doc_id)
        return self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine", "doc_id": doc_id},
        )

    def add(
        self,
        chunks: list[ContextualizedChunk],
        embeddings: list[list[float]],
    ) -> None:
        """
        Add contextualized chunks with their embeddings to the store.
        
        Args:
            chunks: List of ContextualizedChunk objects
            embeddings: Corresponding embedding vectors
        """
        if not chunks or not embeddings:
            return

        if len(chunks) != len(embeddings):
            raise ValueError(
                f"Number of chunks ({len(chunks)}) must match "
                f"number of embeddings ({len(embeddings)})"
            )
        
        # Group chunks by document
        doc_chunks = {}
        for i, chunk in enumerate(chunks):
            if chunk.doc_id not in doc_chunks:
                doc_chunks[chunk.doc_id] = []
            doc_chunks[chunk.doc_id].append((chunk, embeddings[i]))
        
        # Add to separate collections per document
        for doc_id, chunk_embedding_pairs in doc_chunks.items():
            collection = self._get_or_create_collection(doc_id)
            doc_chunks_list = [pair[0] for pair in chunk_embedding_pairs]
            doc_embeddings = [pair[1] for pair in chunk_embedding_pairs]
            
            collection.add(
                ids=[chunk.chunk_id for chunk in doc_chunks_list],
                embeddings=doc_embeddings,
                documents=[chunk.contextualized_text for chunk in doc_chunks_list],
                metadatas=[
                    {
                        "doc_id": chunk.doc_id,
                        "chunk_index": chunk.index,
                        "original_text": chunk.original_text[:1000],
                        "context": chunk.context,
                        "page_summary": chunk.page_summary[:500] if chunk.page_summary else "",
                        **{k: str(v) for k, v in chunk.metadata.items()},
                    }
                    for chunk in doc_chunks_list
                ],
            )

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 100,
        filter_doc_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Search for similar chunks using vector similarity.
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            filter_doc_id: Optional document ID to search within (required for per-doc collections)
            
        Returns:
            List of SearchResult objects sorted by similarity
        """
        if not filter_doc_id:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning("No filter_doc_id provided - cannot search without document ID")
            return []
        
        try:
            collection = self._get_or_create_collection(filter_doc_id)
            
            # Check if collection has any data
            if collection.count() == 0:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Collection for document {filter_doc_id} is empty")
                return []
            
            results = collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
            )
            return self._format_results(results)
        except Exception as e:
            error_msg = str(e)
            # Handle ChromaDB internal errors (often corruption)
            if "Error finding id" in error_msg or "Internal error" in error_msg:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"ChromaDB search error (possibly corrupted index): {e}")
                if filter_doc_id:
                    logger.warning(f"Document {filter_doc_id} may need reindexing")
                return []
            raise

    def _format_results(self, results: dict[str, Any]) -> list[SearchResult]:
        """Convert ChromaDB results to SearchResult objects."""
        search_results = []
        
        if not results["ids"] or not results["ids"][0]:
            return search_results

        ids = results["ids"][0]
        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        for i, chunk_id in enumerate(ids):
            metadata = metadatas[i] if i < len(metadatas) else {}
            distance = distances[i] if i < len(distances) else 0.0
            score = 1 - distance
            
            search_results.append(
                SearchResult(
                    doc_id=metadata.get("doc_id", ""),
                    chunk_index=int(metadata.get("chunk_index", 0)),
                    text=documents[i] if i < len(documents) else "",
                    original_text=metadata.get("original_text", ""),
                    context=metadata.get("context", ""),
                    score=score,
                    metadata=metadata,
                )
            )

        return search_results

    def delete_document(self, doc_id: str) -> int:
        """
        Delete all chunks for a document by deleting its collection.
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            Number of chunks deleted
        """
        try:
            collection_name = self._get_collection_name(doc_id)
            collection = self.client.get_collection(collection_name)
            count = collection.count()
            self.client.delete_collection(collection_name)
            return count
        except Exception:
            return 0

    def get_document_chunks(self, doc_id: str) -> list[dict[str, Any]]:
        """
        Get all chunks for a document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            List of chunk data dictionaries
        """
        try:
            collection = self._get_or_create_collection(doc_id)
            results = collection.get(
                include=["documents", "metadatas"],
            )
            
            chunks = []
            for i, chunk_id in enumerate(results["ids"]):
                chunks.append({
                    "chunk_id": chunk_id,
                    "text": results["documents"][i] if results["documents"] else "",
                    "metadata": results["metadatas"][i] if results["metadatas"] else {},
                })
            
            return chunks
        except Exception:
            return []

    def count(self) -> int:
        """Return total number of chunks across all document collections."""
        total = 0
        for collection in self.client.list_collections():
            total += collection.count()
        return total

    def clear(self) -> None:
        """Delete all document collections."""
        for collection in self.client.list_collections():
            self.client.delete_collection(collection.name)
