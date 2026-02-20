"""Main Contextual Retrieval Service facade."""

import logging
import os
from typing import Callable

from .bm25_index import BM25Index
from .chunker import DocumentChunker
from .contextualizer import ChunkContextualizer
from .embedder import OpenAIEmbedder
from .models import ContextualizedChunk, SearchResult
from .reranker import AzureCohereReranker, NoReranker
from .retriever import HybridRetriever
from .vector_store import ChromaVectorStore


logger = logging.getLogger(__name__)


class ContextualRetrievalService:
    """
    Main service facade for Contextual Retrieval.
    
    Orchestrates the full pipeline:
    - Document indexing: chunk → contextualize → embed → store
    - Search: query → hybrid search → rerank → results
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        chroma_persist_directory: str | None = None,
        chroma_collection_name: str | None = None,
        bm25_index_path: str | None = None,
        context_model: str = "gpt-5-mini",
        embedding_model: str = "text-embedding-3-small",
        use_reranking: bool = True,
    ):
        chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "1000"))
        chunk_overlap = chunk_overlap or int(os.getenv("CHUNK_OVERLAP", "200"))
        
        self.chunker = DocumentChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
        
        context_model = os.getenv("CONTEXT_MODEL", context_model)
        self.contextualizer = ChunkContextualizer(model=context_model)
        
        self.embedder = OpenAIEmbedder(model=embedding_model)
        
        self.vector_store = ChromaVectorStore(
            persist_directory=chroma_persist_directory,
            collection_name=chroma_collection_name or "contextual_chunks",
        )
        
        self.bm25_index = BM25Index(storage_path=bm25_index_path)
        
        if use_reranking and os.getenv("CO_API_KEY"):
            self.reranker = AzureCohereReranker()
        else:
            self.reranker = NoReranker()
        
        self.retriever = HybridRetriever(
            vector_store=self.vector_store,
            bm25_index=self.bm25_index,
            embedder=self.embedder,
            reranker=self.reranker,
        )

    def index_document(
        self,
        document_id: str,
        content: str,
        metadata: dict | None = None,
        progress_callback: Callable[[str, int, int], None] | None = None,
    ) -> int:
        """
        Index a document for contextual retrieval.
        
        Pipeline:
        1. Chunk the document
        2. Generate context for each chunk
        3. Generate embeddings
        4. Store in vector DB and BM25 index
        
        Args:
            document_id: Unique identifier for the document
            content: Full text content of the document
            metadata: Optional metadata to attach to chunks
            progress_callback: Optional callback(stage, current, total)
            
        Returns:
            Number of chunks indexed
        """
        logger.info(f"Indexing document {document_id}")
        
        chunks = self.chunker.chunk_with_metadata(
            document_id=document_id,
            content=content,
            metadata=metadata or {},
        )
        
        if not chunks:
            logger.warning(f"No chunks generated for document {document_id}")
            return 0

        logger.info(f"Generated {len(chunks)} chunks for document {document_id}")
        
        if progress_callback:
            progress_callback("contextualizing", 0, len(chunks))

        def context_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback("contextualizing", current, total)

        # Reset stats for new document
        self.contextualizer.reset_stats()
        
        # Use async version for concurrent API calls (much faster)
        contextualized = self.contextualizer.contextualize_chunks_async(
            document=content,
            chunks=chunks,
            progress_callback=context_progress,
        )
        
        # Log cache statistics
        cache_stats = self.contextualizer.get_cache_stats()
        logger.info(
            f"Context generation complete. "
            f"Cache hit rate: {cache_stats['cache_hit_rate']:.1f}%"
        )
        
        logger.info(f"Contextualized {len(contextualized)} chunks")
        
        if progress_callback:
            progress_callback("embedding", 0, len(contextualized))

        texts = [c.contextualized_text for c in contextualized]
        embeddings = self.embedder.embed(texts)
        
        logger.info(f"Generated {len(embeddings)} embeddings")
        
        if progress_callback:
            progress_callback("storing", 0, len(contextualized))

        self.vector_store.add(contextualized, embeddings)
        
        self.bm25_index.add(contextualized)
        
        logger.info(f"Indexed {len(contextualized)} chunks for document {document_id}")
        
        return len(contextualized)

    def search(
        self,
        query: str,
        top_k: int = 20,
        filter_doc_id: str | None = None,
        use_reranking: bool = True,
    ) -> list[SearchResult]:
        """
        Search for relevant chunks.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_doc_id: Optional document ID to search within
            use_reranking: Whether to apply reranking
            
        Returns:
            List of SearchResult objects
        """
        return self.retriever.retrieve(
            query=query,
            top_k_final=top_k,
            filter_doc_id=filter_doc_id,
            use_reranking=use_reranking,
        )

    def search_for_extraction(
        self,
        queries: list[str],
        top_k_per_query: int = 10,
        filter_doc_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Search with multiple queries and deduplicate results.
        
        Useful for schema-based extraction where you want to find
        chunks relevant to multiple fields.
        
        Args:
            queries: List of search queries (one per field)
            top_k_per_query: Results per query before deduplication
            filter_doc_id: Optional document ID to search within
            
        Returns:
            Deduplicated list of SearchResult objects
        """
        seen_chunks: set[str] = set()
        all_results: list[SearchResult] = []
        
        for query in queries:
            results = self.search(
                query=query,
                top_k=top_k_per_query,
                filter_doc_id=filter_doc_id,
            )
            
            for result in results:
                chunk_id = f"{result.doc_id}_{result.chunk_index}"
                if chunk_id not in seen_chunks:
                    seen_chunks.add(chunk_id)
                    all_results.append(result)
        
        all_results.sort(key=lambda r: r.score, reverse=True)
        
        return all_results

    def delete_document(self, document_id: str) -> dict[str, int]:
        """
        Delete a document from the index.
        
        Args:
            document_id: Document ID to delete
            
        Returns:
            Dict with counts of deleted chunks from each store
        """
        vector_deleted = self.vector_store.delete_document(document_id)
        bm25_deleted = self.bm25_index.delete_document(document_id)
        
        logger.info(
            f"Deleted document {document_id}: "
            f"vector={vector_deleted}, bm25={bm25_deleted}"
        )
        
        return {
            "vector_store": vector_deleted,
            "bm25_index": bm25_deleted,
        }

    def get_document_chunks(
        self,
        document_id: str,
    ) -> list[ContextualizedChunk]:
        """
        Get all indexed chunks for a document.
        
        Args:
            document_id: Document ID
            
        Returns:
            List of ContextualizedChunk objects
        """
        chunk_data = self.vector_store.get_document_chunks(document_id)
        
        chunks = []
        for data in chunk_data:
            metadata = data.get("metadata", {})
            chunks.append(
                ContextualizedChunk(
                    doc_id=metadata.get("doc_id", document_id),
                    index=int(metadata.get("chunk_index", 0)),
                    original_text=metadata.get("original_text", ""),
                    context=metadata.get("context", ""),
                    contextualized_text=data.get("text", ""),
                    metadata=metadata,
                )
            )
        
        return sorted(chunks, key=lambda c: c.index)

    def get_stats(self) -> dict:
        """Get statistics about the index."""
        return {
            "vector_store_count": self.vector_store.count(),
            "bm25_index_count": self.bm25_index.count(),
            "reranker_type": type(self.reranker).__name__,
        }


_service_instance: ContextualRetrievalService | None = None


def get_contextual_retrieval_service() -> ContextualRetrievalService:
    """Get or create the singleton service instance."""
    global _service_instance
    
    if _service_instance is None:
        _service_instance = ContextualRetrievalService()
    
    return _service_instance
