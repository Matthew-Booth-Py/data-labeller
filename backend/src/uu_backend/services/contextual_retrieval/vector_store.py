"""ChromaDB vector store for contextual retrieval."""

import os
from typing import Any

import chromadb
from chromadb.config import Settings

from .models import ContextualizedChunk, SearchResult


class ChromaVectorStore:
    """
    ChromaDB-based vector store for storing and searching embeddings.
    
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
        self.collection_name = collection_name or os.getenv(
            "CHROMA_COLLECTION_NAME", "contextual_chunks"
        )
        
        self.client = chromadb.PersistentClient(
            path=self.persist_directory,
            settings=Settings(anonymized_telemetry=False),
        )
        
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
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

        self.collection.add(
            ids=[chunk.chunk_id for chunk in chunks],
            embeddings=embeddings,
            documents=[chunk.contextualized_text for chunk in chunks],
            metadatas=[
                {
                    "doc_id": chunk.doc_id,
                    "chunk_index": chunk.index,
                    "original_text": chunk.original_text[:1000],
                    "context": chunk.context,
                    **{k: str(v) for k, v in chunk.metadata.items()},
                }
                for chunk in chunks
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
            filter_doc_id: Optional document ID to filter results
            
        Returns:
            List of SearchResult objects sorted by similarity
        """
        where_filter = None
        if filter_doc_id:
            where_filter = {"doc_id": filter_doc_id}

        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        return self._format_results(results)

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
        Delete all chunks for a document.
        
        Args:
            doc_id: Document ID to delete
            
        Returns:
            Number of chunks deleted
        """
        results = self.collection.get(
            where={"doc_id": doc_id},
            include=[],
        )
        
        if results["ids"]:
            self.collection.delete(ids=results["ids"])
            return len(results["ids"])
        
        return 0

    def get_document_chunks(self, doc_id: str) -> list[dict[str, Any]]:
        """
        Get all chunks for a document.
        
        Args:
            doc_id: Document ID
            
        Returns:
            List of chunk data dictionaries
        """
        results = self.collection.get(
            where={"doc_id": doc_id},
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

    def count(self) -> int:
        """Return total number of chunks in the store."""
        return self.collection.count()

    def clear(self) -> None:
        """Delete all chunks from the collection."""
        self.client.delete_collection(self.collection_name)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
