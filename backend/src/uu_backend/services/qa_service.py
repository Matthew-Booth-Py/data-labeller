"""Question-answering service using RAG (Retrieval-Augmented Generation)."""

import logging

from neo4j import GraphDatabase
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.indexes import create_vector_index
from neo4j_graphrag.llm.openai_llm import OpenAILLM
from neo4j_graphrag.retrievers import VectorCypherRetriever
from neo4j_graphrag.types import RetrieverResultItem

from uu_backend.config import get_settings
from uu_backend.database.vector_store import get_vector_store

logger = logging.getLogger(__name__)


class QAService:
    """Service for answering questions about documents using RAG."""

    _VECTOR_RETRIEVAL_QUERY = """
    OPTIONAL MATCH (node)-[:FROM_DOCUMENT]->(doc:Document)
    WHERE size($document_ids) = 0 OR doc.id IN $document_ids
    RETURN
      coalesce(node.text, "") AS chunk_text,
      coalesce(doc.id, "") AS document_id,
      coalesce(doc.filename, doc.path, "Unknown") AS filename,
      toInteger(coalesce(node.index, 0)) AS chunk_index,
      score AS similarity
    """

    def __init__(self):
        self.settings = get_settings()
        self.model = self.settings.openai_model
        self._neo4j_driver = None
        self._retriever = None
        self._graphrag = None
        self._vector_index_ready = False

    @staticmethod
    def _record_to_retriever_item(record) -> RetrieverResultItem:
        text = str(record.get("chunk_text") or "")
        similarity = float(record.get("similarity") or 0.0)
        metadata = {
            "document_id": str(record.get("document_id") or ""),
            "filename": str(record.get("filename") or "Unknown"),
            "chunk_index": int(record.get("chunk_index") or 0),
            "similarity": similarity,
        }
        return RetrieverResultItem(
            content=text,
            metadata=metadata,
        )

    def _ensure_chunk_vector_index(self) -> None:
        if self._vector_index_ready:
            return

        similarity = (self.settings.graphrag_similarity_fn or "cosine").lower()
        if similarity not in {"cosine", "euclidean"}:
            similarity = "cosine"

        create_vector_index(
            driver=self._neo4j_driver,
            name=self.settings.graphrag_vector_index_name,
            label="Chunk",
            embedding_property="embedding",
            dimensions=self.settings.graphrag_embedding_dimensions,
            similarity_fn=similarity,
            fail_if_exists=False,
            neo4j_database=self.settings.neo4j_database,
        )
        self._vector_index_ready = True

    def _get_graphrag(self) -> GraphRAG:
        if self._graphrag is not None:
            return self._graphrag

        if not self.settings.openai_api_key:
            raise RuntimeError("GraphRAG Q&A requires OPENAI_API_KEY")

        self._neo4j_driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )
        self._ensure_chunk_vector_index()

        embedder = OpenAIEmbeddings(
            model=self.settings.graphrag_embedding_model,
            api_key=self.settings.openai_api_key,
        )
        self._retriever = VectorCypherRetriever(
            driver=self._neo4j_driver,
            index_name=self.settings.graphrag_vector_index_name,
            retrieval_query=self._VECTOR_RETRIEVAL_QUERY,
            embedder=embedder,
            result_formatter=self._record_to_retriever_item,
            neo4j_database=self.settings.neo4j_database,
        )
        llm = OpenAILLM(
            model_name=self.model,
            api_key=self.settings.openai_api_key,
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
        rag = self._get_graphrag()
        rag_result = rag.search(
            query_text=question,
            retriever_config={
                "top_k": n_context,
                "query_params": {"document_ids": document_ids or []},
            },
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
