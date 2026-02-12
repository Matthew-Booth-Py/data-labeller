"""Question-answering service using RAG (Retrieval-Augmented Generation)."""

import logging
from typing import Any

from neo4j import GraphDatabase
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.llm.openai_llm import OpenAILLM
from neo4j_graphrag.retrievers import Text2CypherRetriever
from neo4j_graphrag.types import RawSearchResult, RetrieverResultItem

from uu_backend.config import get_settings
from uu_backend.database.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class _TopKText2CypherRetriever(Text2CypherRetriever):
    """Text2Cypher retriever with deterministic top-k result trimming."""

    def get_search_results(
        self,
        query_text: str,
        prompt_params: dict[str, Any] | None = None,
        top_k: int | None = None,
    ) -> RawSearchResult:
        result = super().get_search_results(
            query_text=query_text,
            prompt_params=prompt_params,
        )
        if top_k is None:
            return result
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        result.records = result.records[:top_k]
        return result


class QAService:
    """Service for answering questions about documents using RAG."""

    def __init__(self):
        self.settings = get_settings()
        self.model = self.settings.openai_model
        self._neo4j_driver = None
        self._retriever = None
        self._graphrag = None

    @staticmethod
    def _record_to_retriever_item(record) -> RetrieverResultItem:
        record_data = record.data() if hasattr(record, "data") else {}
        content = str(record_data) if record_data else str(record)

        similarity_value = record_data.get("similarity", 0.0)
        try:
            similarity = float(similarity_value or 0.0)
        except (TypeError, ValueError):
            similarity = 0.0

        chunk_index_value = record_data.get("chunk_index", 0)
        try:
            chunk_index = int(chunk_index_value or 0)
        except (TypeError, ValueError):
            chunk_index = 0

        metadata = {
            "document_id": str(record_data.get("document_id") or ""),
            "filename": str(record_data.get("filename") or "Unknown"),
            "chunk_index": chunk_index,
            "similarity": similarity,
        }
        return RetrieverResultItem(
            content=content,
            metadata=metadata,
        )

    def _get_graphrag(self) -> GraphRAG:
        if self._graphrag is not None:
            return self._graphrag

        if not self.settings.openai_api_key:
            raise RuntimeError("GraphRAG Q&A requires OPENAI_API_KEY")

        self._neo4j_driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )
        llm = OpenAILLM(
            model_name=self.model,
            api_key=self.settings.openai_api_key,
        )
        self._retriever = _TopKText2CypherRetriever(
            llm=llm,
            driver=self._neo4j_driver,
            result_formatter=self._record_to_retriever_item,
            neo4j_database=self.settings.neo4j_database,
        )
        self._graphrag = GraphRAG(retriever=self._retriever, llm=llm)
        return self._graphrag

    @staticmethod
    def _confidence_from_sources(sources: list[dict]) -> float:
        if not sources:
            return 0.0
        sims = [float(source.get("similarity") or 0.0) for source in sources]
        sims = [s for s in sims if s > 0]
        if not sims:
            return 0.5
        top = sorted(sims, reverse=True)[:3]
        return max(0.0, min(1.0, sum(top) / len(top)))

    def semantic_search(
        self,
        query: str,
        n_results: int = 5,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        """
        Search for relevant document chunks.
        
        Args:
            query: The search query
            n_results: Maximum number of results
            document_ids: Optional filter to specific documents
            
        Returns:
            List of search results with content and metadata
        """
        vector_store = get_vector_store()
        return vector_store.semantic_search(query, n_results, document_ids)

    def _ask_with_graphrag(
        self,
        *,
        question: str,
        document_ids: list[str] | None,
        n_context: int,
    ) -> dict:
        if document_ids:
            raise ValueError(
                "document_ids filtering is not supported with Text2CypherRetriever"
            )

        rag = self._get_graphrag()
        rag_result = rag.search(
            query_text=question,
            retriever_config={"top_k": n_context},
            return_context=True,
        )

        retriever_items = []
        if rag_result.retriever_result and rag_result.retriever_result.items:
            retriever_items = rag_result.retriever_result.items

        sources = []
        for item in retriever_items:
            metadata = item.metadata or {}
            content = str(item.content or "")
            sources.append(
                {
                    "document_id": str(metadata.get("document_id") or ""),
                    "filename": str(metadata.get("filename") or "Unknown"),
                    "chunk_index": int(metadata.get("chunk_index") or 0),
                    "similarity": float(metadata.get("similarity") or 0.0),
                    "excerpt": content[:200] + "..." if len(content) > 200 else content,
                }
            )

        return {
            "answer": rag_result.answer,
            "confidence": self._confidence_from_sources(sources),
            "sources": sources,
            "referenced_sources": [idx + 1 for idx in range(len(sources))],
        }

    def ask(
        self,
        question: str,
        document_ids: list[str] | None = None,
        n_context: int = 5,
    ) -> dict:
        """
        Answer a question using RAG (Retrieval-Augmented Generation).
        
        Args:
            question: The question to answer
            document_ids: Optional list of document IDs to search within
            n_context: Number of context chunks to retrieve
            
        Returns:
            Dictionary with answer, sources, and confidence
        """
        if not self.settings.openai_api_key:
            raise RuntimeError("GraphRAG Q&A requires OPENAI_API_KEY")
        return self._ask_with_graphrag(
            question=question,
            document_ids=document_ids,
            n_context=n_context,
        )


# Singleton instance
_qa_service: QAService | None = None


def get_qa_service() -> QAService:
    """Get or create the QA service singleton."""
    global _qa_service
    if _qa_service is None:
        _qa_service = QAService()
    return _qa_service
