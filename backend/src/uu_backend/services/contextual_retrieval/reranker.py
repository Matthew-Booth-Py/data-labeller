"""Azure Cohere reranker for contextual retrieval."""

import logging
import os
from typing import Protocol

import requests

from .models import SearchResult

logger = logging.getLogger(__name__)


class Reranker(Protocol):
    """Protocol for reranker implementations."""

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int = 20,
    ) -> list[SearchResult]:
        """Rerank search results by relevance to query."""
        ...


class AzureCohereReranker:
    """
    Reranker using Azure-hosted Cohere API.

    Uses your Azure endpoint instead of the standard Cohere API.
    """

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        model: str = "Cohere-rerank-v4.0-fast",
        timeout: int = 30,
    ):
        self.api_key = api_key or os.getenv("CO_API_KEY")
        self.endpoint = endpoint or os.getenv(
            "CO_RERANK_ENDPOINT",
            "https://mbaistudio3062596349.services.ai.azure.com/providers/cohere/v2/rerank",
        )
        self.model = model
        self.timeout = timeout

        if not self.api_key:
            raise ValueError("CO_API_KEY environment variable is required")

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int = 20,
    ) -> list[SearchResult]:
        """
        Rerank search results using Azure Cohere.

        Args:
            query: Search query
            results: List of SearchResult objects to rerank
            top_n: Number of top results to return

        Returns:
            Reranked list of SearchResult objects
        """
        if not results:
            return []

        if len(results) <= 1:
            return results

        logger.info(
            f"[Reranker] Reranking {len(results)} candidates with Azure Cohere (top_n={top_n})"
        )

        documents = [r.text for r in results]

        reranked_indices = self._call_rerank_api(query, documents, top_n)

        logger.info(f"[Reranker] Received {len(reranked_indices)} reranked results")
        if reranked_indices:
            logger.info(
                f"[Reranker] Top relevance score: {reranked_indices[0]['relevance_score']:.4f}"
            )

        reranked_results = []
        for item in reranked_indices:
            idx = item["index"]
            relevance_score = item["relevance_score"]

            if idx < len(results):
                result = results[idx]
                reranked_results.append(
                    SearchResult(
                        doc_id=result.doc_id,
                        chunk_index=result.chunk_index,
                        text=result.text,
                        original_text=result.original_text,
                        context=result.context,
                        score=relevance_score,
                        metadata=result.metadata,
                    )
                )

        return reranked_results

    def _call_rerank_api(
        self,
        query: str,
        documents: list[str],
        top_n: int,
    ) -> list[dict]:
        """Call the Azure Cohere rerank API."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # Truncate documents to avoid exceeding limits
        truncated_docs = [doc[:4000] for doc in documents]

        payload = {
            "model": self.model,
            "query": query,
            "documents": truncated_docs,
            "top_n": min(top_n, len(truncated_docs)),
        }

        response = requests.post(
            self.endpoint,
            headers=headers,
            json=payload,
            timeout=self.timeout,
        )

        if not response.ok:
            print(f"Rerank API error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            response.raise_for_status()

        return response.json().get("results", [])


class NoReranker:
    """
    Pass-through reranker that doesn't rerank.

    Useful for testing or when reranking is not needed.
    """

    def rerank(
        self,
        query: str,
        results: list[SearchResult],
        top_n: int = 20,
    ) -> list[SearchResult]:
        """Return top_n results without reranking."""
        return results[:top_n]
