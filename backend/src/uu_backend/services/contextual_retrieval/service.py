"""Main Contextual Retrieval Service facade."""

import logging
import os
from collections.abc import Callable

from uu_backend.config import get_settings

from .bm25_index import BM25Index
from .chunker import DocumentChunker, PageAwareChunker
from .contextualizer import ChunkContextualizer
from .embedder import OpenAIEmbedder
from .models import ContextualizedChunk, SearchResult
from .page_summarizer import PageSummarizer
from .reranker import AzureCohereReranker, NoReranker
from .retriever import HybridRetriever
from .vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class ContextualRetrievalService:
    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
        chroma_persist_directory: str | None = None,
        chroma_collection_name: str | None = None,
        bm25_index_path: str | None = None,
        context_model: str | None = None,
        embedding_model: str = "text-embedding-3-small",
        use_reranking: bool = True,
        chunking_strategy: str | None = None,
    ):
        settings = get_settings()
        chunking_strategy = chunking_strategy or os.getenv("CHUNKING_STRATEGY", "page")

        if chunking_strategy == "page":
            self.chunker = PageAwareChunker(
                max_page_size=int(os.getenv("MAX_PAGE_SIZE", "8000")),
                fallback_chunk_size=int(os.getenv("CHUNK_SIZE", "2000")),
                fallback_chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
            )
            logger.info("Chunking strategy: page-aware")
        else:
            chunk_size = chunk_size or int(os.getenv("CHUNK_SIZE", "1000"))
            chunk_overlap = chunk_overlap or int(os.getenv("CHUNK_OVERLAP", "200"))
            self.chunker = DocumentChunker(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )
            logger.info(f"Chunking strategy: fixed-size ({chunk_size} chars)")

        context_model = context_model or settings.effective_context_model
        self.contextualizer = ChunkContextualizer(model=context_model)

        summary_model = settings.effective_summary_model
        self.page_summarizer = PageSummarizer(model=summary_model)

        self.embedder = OpenAIEmbedder(model=embedding_model)

        self.vector_store = ChromaVectorStore(
            persist_directory=chroma_persist_directory,
            collection_name=chroma_collection_name or "contextual_chunks",
        )

        self.bm25_index = BM25Index(storage_path=bm25_index_path)

        if use_reranking and os.getenv("CO_API_KEY"):
            self.reranker = AzureCohereReranker()
            logger.info("✓ Reranker enabled: Azure Cohere")
        else:
            self.reranker = NoReranker()
            logger.info("✗ Reranker disabled (no CO_API_KEY or use_reranking=False)")

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
            progress_callback("summarizing", 0, len(chunks))

        def summary_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback("summarizing", current, total)

        page_summaries = self.page_summarizer.summarize_pages_async(
            chunks=chunks,
            progress_callback=summary_progress,
        )

        logger.info(f"Generated {len(page_summaries)} page summaries")

        if progress_callback:
            progress_callback("contextualizing", 0, len(chunks))

        def context_progress(current: int, total: int) -> None:
            if progress_callback:
                progress_callback("contextualizing", current, total)

        self.contextualizer.reset_stats()

        contextualized = self.contextualizer.contextualize_chunks_async(
            document=content,
            chunks=chunks,
            progress_callback=context_progress,
        )

        cache_stats = self.contextualizer.get_cache_stats()
        logger.info(
            f"Context generation complete. " f"Cache hit rate: {cache_stats['cache_hit_rate']:.1f}%"
        )

        logger.info(f"Contextualized {len(contextualized)} chunks")

        for chunk, summary in zip(contextualized, page_summaries):
            chunk.page_summary = summary
            chunk.contextualized_text = f"{summary}\n\n{chunk.context}\n\n{chunk.original_text}"

        logger.info("Merged page summaries into contextualized chunks")

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
        logger.info(
            f"Search query: '{query[:100]}...' | top_k={top_k} | doc_filter={filter_doc_id} | rerank={use_reranking}"
        )

        results = self.retriever.retrieve(
            query=query,
            top_k_final=top_k,
            filter_doc_id=filter_doc_id,
            use_reranking=use_reranking,
        )

        logger.info(f"Search returned {len(results)} results")
        return results

    def search_for_extraction(
        self,
        queries: list[str],
        top_k_per_query: int = 10,
        filter_doc_id: str | None = None,
    ) -> list[SearchResult]:
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
        vector_deleted = self.vector_store.delete_document(document_id)
        bm25_deleted = self.bm25_index.delete_document(document_id)

        logger.info(
            f"Deleted document {document_id}: " f"vector={vector_deleted}, bm25={bm25_deleted}"
        )

        return {
            "vector_store": vector_deleted,
            "bm25_index": bm25_deleted,
        }

    def get_document_chunks(
        self,
        document_id: str,
    ) -> list[ContextualizedChunk]:
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
        return {
            "vector_store_count": self.vector_store.count(),
            "bm25_index_count": self.bm25_index.count(),
            "reranker_type": type(self.reranker).__name__,
        }


_service_instance: ContextualRetrievalService | None = None


def get_contextual_retrieval_service() -> ContextualRetrievalService:
    global _service_instance
    if _service_instance is None:
        _service_instance = ContextualRetrievalService()
    return _service_instance
