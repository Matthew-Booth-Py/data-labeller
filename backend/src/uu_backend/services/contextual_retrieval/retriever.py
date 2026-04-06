"""Hybrid retriever combining vector search, BM25, and reranking."""

import logging

from .bm25_index import BM25Index
from .embedder import OpenAIEmbedder
from .models import SearchResult
from .reranker import AzureCohereReranker, NoReranker
from .vector_store import ChromaVectorStore

logger = logging.getLogger(__name__)


class HybridRetriever:
    """
    Combines vector search and BM25 with Reciprocal Rank Fusion.

    Pipeline:
    1. Vector search (semantic similarity)
    2. BM25 search (keyword matching)
    3. Reciprocal Rank Fusion (combine results)
    4. Reranking (optional, improves precision)
    """

    def __init__(
        self,
        vector_store: ChromaVectorStore,
        bm25_index: BM25Index,
        embedder: OpenAIEmbedder,
        reranker: AzureCohereReranker | NoReranker | None = None,
    ):
        self.vector_store = vector_store
        self.bm25_index = bm25_index
        self.embedder = embedder
        self.reranker = reranker or NoReranker()

    def retrieve(
        self,
        query: str,
        top_k_initial: int = 150,
        top_k_final: int = 20,
        filter_doc_id: str | None = None,
        use_reranking: bool = True,
    ) -> list[SearchResult]:
        """Retrieve relevant chunks using hybrid search.

        Parameters
        ----------
        query : str
            Search query.
        top_k_initial : int
            Number of candidates fetched from each search method.
        top_k_final : int
            Final number of results returned after reranking.
        filter_doc_id : str, optional
            Restrict results to a specific document.
        use_reranking : bool
            Whether to apply reranking on the fused candidates.

        Returns
        -------
        list[SearchResult]
            Results sorted by relevance.
        """
        logger.debug("[Retriever] Embedding query...")
        query_embedding = self.embedder.embed_query(query)

        logger.debug(f"[Retriever] Vector search (top_k={top_k_initial})...")
        vector_results = self.vector_store.search(
            query_embedding,
            top_k=top_k_initial,
            filter_doc_id=filter_doc_id,
        )
        logger.debug(f"[Retriever] Vector search returned {len(vector_results)} results")

        logger.debug(f"[Retriever] BM25 search (top_k={top_k_initial})...")
        bm25_results = self.bm25_index.search(
            query,
            top_k=top_k_initial,
            filter_doc_id=filter_doc_id,
        )
        logger.debug(f"[Retriever] BM25 search returned {len(bm25_results)} results")

        logger.debug("[Retriever] Applying Reciprocal Rank Fusion...")
        fused_results = self._reciprocal_rank_fusion(
            vector_results,
            bm25_results,
        )
        logger.debug(f"[Retriever] RRF produced {len(fused_results)} unique results")

        if use_reranking and len(fused_results) > 1:
            candidates = fused_results[:top_k_initial]
            logger.debug(
                f"[Retriever] Reranking {len(candidates)} candidates to top {top_k_final}..."
            )
            reranked = self.reranker.rerank(query, candidates, top_n=top_k_final)
            logger.debug(f"[Retriever] Reranking returned {len(reranked)} results")
            return reranked

        logger.debug(f"[Retriever] Returning top {top_k_final} fused results (no reranking)")
        return fused_results[:top_k_final]

    def retrieve_vector_only(
        self,
        query: str,
        top_k: int = 20,
        filter_doc_id: str | None = None,
    ) -> list[SearchResult]:
        """Retrieve using only vector search (no BM25 or reranking).

        Parameters
        ----------
        query : str
            Search query.
        top_k : int
            Number of results to return.
        filter_doc_id : str, optional
            Restrict results to a specific document.

        Returns
        -------
        list[SearchResult]
            Vector-ranked results.
        """
        query_embedding = self.embedder.embed_query(query)
        return self.vector_store.search(
            query_embedding,
            top_k=top_k,
            filter_doc_id=filter_doc_id,
        )

    def retrieve_bm25_only(
        self,
        query: str,
        top_k: int = 20,
        filter_doc_id: str | None = None,
    ) -> list[SearchResult]:
        """Retrieve using only BM25 keyword search (no vector search or reranking).

        Parameters
        ----------
        query : str
            Search query.
        top_k : int
            Number of results to return.
        filter_doc_id : str, optional
            Restrict results to a specific document.

        Returns
        -------
        list[SearchResult]
            BM25-ranked results.
        """
        return self.bm25_index.search(
            query,
            top_k=top_k,
            filter_doc_id=filter_doc_id,
        )

    def _reciprocal_rank_fusion(
        self,
        *result_lists: list[SearchResult],
        k: int = 60,
    ) -> list[SearchResult]:
        scores: dict[str, dict] = {}

        for results in result_lists:
            for rank, result in enumerate(results):
                chunk_id = f"{result.doc_id}_{result.chunk_index}"

                if chunk_id not in scores:
                    scores[chunk_id] = {
                        "result": result,
                        "score": 0.0,
                    }

                scores[chunk_id]["score"] += 1.0 / (k + rank + 1)

        sorted_items = sorted(
            scores.values(),
            key=lambda x: x["score"],
            reverse=True,
        )

        fused_results = []
        for item in sorted_items:
            result = item["result"]
            fused_results.append(
                SearchResult(
                    doc_id=result.doc_id,
                    chunk_index=result.chunk_index,
                    text=result.text,
                    original_text=result.original_text,
                    context=result.context,
                    score=item["score"],
                    metadata=result.metadata,
                )
            )

        return fused_results
