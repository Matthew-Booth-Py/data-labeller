"""Question-answering service using Neo4j's HybridCypherRetriever.

Uses Neo4j's official HybridCypherRetriever which combines:
1. Vector search on entity embeddings for semantic similarity
2. Full-text search on entity names and context for lexical matching
3. Graph traversal via Cypher to retrieve related entities and relationships
4. LLM-based answer generation from retrieved context
"""

import logging
import os
from typing import Any

from neo4j import GraphDatabase
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.llm.openai_llm import OpenAILLM
from neo4j_graphrag.retrievers import HybridCypherRetriever

from uu_backend.config import get_settings

logger = logging.getLogger(__name__)


class QAService:
    """Service for answering questions about documents using HybridCypherRetriever."""

    NO_EVIDENCE_ANSWER = "I could not find evidence in the indexed graph to answer that question."
    
    # Index names
    VECTOR_INDEX = "entity_embeddings"
    FULLTEXT_INDEX = "entity_fulltext"

    def __init__(self):
        self.settings = get_settings()
        self.model = self.settings.openai_model
        self._neo4j_driver = None
        self._llm = None
        self._embedder = None
        self._retriever = None
        self._graphrag = None

    def _get_driver(self):
        """Get or create Neo4j driver."""
        if self._neo4j_driver is None:
            self._neo4j_driver = GraphDatabase.driver(
                self.settings.neo4j_uri,
                auth=(self.settings.neo4j_user, self.settings.neo4j_password),
            )
        return self._neo4j_driver

    def _get_embedder(self) -> OpenAIEmbeddings:
        """Get or create embedder instance."""
        if self._embedder is None:
            if not self.settings.openai_api_key:
                raise RuntimeError("Q&A requires OPENAI_API_KEY")
            # Set env var for the OpenAIEmbeddings client
            os.environ["OPENAI_API_KEY"] = self.settings.openai_api_key
            self._embedder = OpenAIEmbeddings(model="text-embedding-3-small")
        return self._embedder

    def _get_llm(self) -> OpenAILLM:
        """Get or create LLM instance."""
        if self._llm is None:
            if not self.settings.openai_api_key:
                raise RuntimeError("Q&A requires OPENAI_API_KEY")
            self._llm = OpenAILLM(
                model_name=self.model,
                api_key=self.settings.openai_api_key,
            )
        return self._llm

    def _get_retrieval_query(self) -> str:
        """
        Build the Cypher query for graph traversal after hybrid search.
        
        This query enriches each entity node found by hybrid search with:
        - Document information
        - Related entities through relationships
        - Relationship types and context
        """
        return """
        // Get document info
        OPTIONAL MATCH (d:Document)-[:MENTIONS]->(node)
        
        // Get related entities through relationships
        OPTIONAL MATCH (node)-[rel:INVOLVED_IN|LOCATED_AT|COMMUNICATED_WITH]-(related:Entity)
        
        RETURN
            node.name AS entity_name,
            node.type AS entity_type,
            node.context AS entity_context,
            d.id AS document_id,
            d.filename AS filename,
            collect(DISTINCT {
                relationship: type(rel),
                related_name: related.name,
                related_type: related.type,
                related_context: related.context
            })[0..5] AS relationships
        """

    def _get_retriever(self) -> HybridCypherRetriever:
        """Get or create HybridCypherRetriever instance."""
        if self._retriever is None:
            driver = self._get_driver()
            embedder = self._get_embedder()
            
            self._retriever = HybridCypherRetriever(
                driver=driver,
                vector_index_name=self.VECTOR_INDEX,
                fulltext_index_name=self.FULLTEXT_INDEX,
                retrieval_query=self._get_retrieval_query(),
                embedder=embedder,
            )
        return self._retriever

    def _get_graphrag(self) -> GraphRAG:
        """Get or create GraphRAG pipeline."""
        if self._graphrag is None:
            retriever = self._get_retriever()
            llm = self._get_llm()
            self._graphrag = GraphRAG(retriever=retriever, llm=llm)
        return self._graphrag

    @staticmethod
    def _parse_record_content(content_str: str) -> dict[str, Any]:
        """Parse Neo4j Record string representation to extract fields."""
        import re
        
        # Content is like: <Record entity_name='Foo' entity_type='Bar' ...>
        # Extract key-value pairs
        data = {}
        
        # Match patterns like entity_name='value' or entity_name=None or entity_name=['list', 'items']
        pattern = r"(\w+)=(?:'([^']*)'|(\[.*?\])|([^'\s][^\s]*)(?=\s+\w+=|>))"
        matches = re.findall(pattern, content_str)
        
        for match in matches:
            key = match[0]
            # match[1] is single-quoted value, match[2] is list, match[3] is unquoted value
            if match[1]:  # Single-quoted string
                value = match[1]
            elif match[2]:  # List
                try:
                    import ast
                    value = ast.literal_eval(match[2])
                except Exception:
                    value = match[2]
            elif match[3]:  # Unquoted value (None, numbers, etc.)
                if match[3] == 'None':
                    value = None
                else:
                    value = match[3]
            else:
                value = None
            
            data[key] = value
        
        return data
    
    @staticmethod
    def _build_excerpt_from_result(data: dict[str, Any]) -> str:
        """Build a readable excerpt from retriever result."""
        parts = []
        
        # Entity info
        entity_name = data.get("entity_name") or "Unknown"
        entity_type = data.get("entity_type") or "Entity"
        context = data.get("entity_context") or ""
        
        parts.append(f"{entity_name} ({entity_type})")
        if context:
            parts.append(f"Context: {context}")
        
        # Relationships
        relationships = data.get("relationships") or []
        if isinstance(relationships, str):
            # Try to parse if it's a string representation
            try:
                import ast
                relationships = ast.literal_eval(relationships)
            except Exception:
                relationships = []
        
        for rel in relationships:
            if rel and isinstance(rel, dict) and rel.get("related_name"):
                rel_type = rel.get("relationship") or "RELATED_TO"
                related_name = rel.get("related_name")
                related_type = rel.get("related_type") or "Entity"
                parts.append(f"{rel_type} {related_name} ({related_type})")
        
        return " | ".join(parts)

    @staticmethod
    def _confidence_from_sources(sources: list[dict]) -> float:
        """Calculate confidence score from source similarities."""
        if not sources:
            return 0.0
        scores = [float(source.get("score") or source.get("similarity") or 0.0) for source in sources]
        scores = [s for s in scores if s > 0]
        if not scores:
            return 0.0
        top = sorted(scores, reverse=True)[:3]
        return max(0.0, min(1.0, sum(top) / len(top)))

    def ask(
        self,
        question: str,
        document_ids: list[str] | None = None,
        n_context: int = 10,
    ) -> dict:
        """
        Answer a question using HybridCypherRetriever.
        
        Uses Neo4j's official HybridCypherRetriever which:
        1. Performs hybrid search (vector + full-text) on entities
        2. Executes Cypher query to get related entities via graph traversal
        3. Returns enriched context for LLM to generate answer
        
        Args:
            question: The question to answer
            document_ids: Optional list of document IDs to filter results
            n_context: Number of context items to retrieve
            
        Returns:
            Dictionary with answer, sources, and confidence
        """
        if not self.settings.openai_api_key:
            raise RuntimeError("Q&A requires OPENAI_API_KEY")
        
        # Get GraphRAG pipeline with HybridCypherRetriever
        rag = self._get_graphrag()
        
        try:
            # Execute hybrid search + graph traversal + answer generation
            result = rag.search(
                query_text=question,
                retriever_config={"top_k": n_context},
                return_context=True,
            )
            
            # Extract sources from retriever results
            sources = []
            if result.retriever_result and result.retriever_result.items:
                for item in result.retriever_result.items:
                    # Parse the content (Neo4j Record string representation)
                    content_str = str(item.content or "")
                    content_data = self._parse_record_content(content_str)
                    
                    metadata = item.metadata or {}
                    excerpt = self._build_excerpt_from_result(content_data)
                    
                    sources.append({
                        "document_id": content_data.get("document_id") or "",
                        "filename": content_data.get("filename") or "Unknown",
                        "similarity": float(metadata.get("score") or 0.0),
                        "excerpt": excerpt,
                    })
            
            # Filter by document_ids if specified
            if document_ids:
                sources = [s for s in sources if s["document_id"] in document_ids]
            
            return {
                "answer": result.answer or self.NO_EVIDENCE_ANSWER,
                "confidence": self._confidence_from_sources(sources),
                "sources": sources,
                "referenced_sources": list(range(1, len(sources) + 1)),
            }
            
        except Exception as e:
            logger.error(f"HybridCypherRetriever failed: {e}", exc_info=True)
            return {
                "answer": self.NO_EVIDENCE_ANSWER,
                "confidence": 0.0,
                "sources": [],
                "referenced_sources": [],
            }

    def semantic_search(
        self,
        query: str,
        n_results: int = 5,
        document_ids: list[str] | None = None,
    ) -> list[dict]:
        """
        Search for relevant entities in the knowledge graph.
        
        Uses the HybridCypherRetriever for search.
        
        Args:
            query: The search query
            n_results: Maximum number of results
            document_ids: Optional filter to specific documents
            
        Returns:
            List of search results with entity info and relevance scores
        """
        retriever = self._get_retriever()
        
        try:
            result = retriever.search(query_text=query, top_k=n_results)
            
            search_results = []
            for item in result.items:
                content_str = str(item.content or "")
                content_data = self._parse_record_content(content_str)
                
                metadata = item.metadata or {}
                
                # Filter by document_ids if specified
                doc_id = content_data.get("document_id") or ""
                if document_ids and doc_id not in document_ids:
                    continue
                
                search_results.append({
                    "document_id": doc_id,
                    "filename": content_data.get("filename") or "Unknown",
                    "entity_name": content_data.get("entity_name") or "Unknown",
                    "entity_type": content_data.get("entity_type") or "Entity",
                    "similarity": float(metadata.get("score") or 0.0),
                    "content": self._build_excerpt_from_result(content_data),
                })
            
            return search_results[:n_results]
            
        except Exception as e:
            logger.error(f"Semantic search failed: {e}", exc_info=True)
            return []


# Singleton instance
_qa_service: QAService | None = None


def get_qa_service() -> QAService:
    """Get or create the QA service singleton."""
    global _qa_service
    if _qa_service is None:
        _qa_service = QAService()
    return _qa_service
