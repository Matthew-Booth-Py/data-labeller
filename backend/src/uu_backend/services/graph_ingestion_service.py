"""Graph ingestion orchestration for Neo4j writes."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from neo4j import GraphDatabase
from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
from neo4j_graphrag.experimental.components.types import LexicalGraphConfig
from neo4j_graphrag.experimental.pipeline.kg_builder import SimpleKGPipeline
from neo4j_graphrag.indexes import create_vector_index
from neo4j_graphrag.llm.openai_llm import OpenAILLM

from uu_backend.config import get_settings
from uu_backend.database.neo4j_client import GRAPH_VERSION, Neo4jClient, get_neo4j_client
from uu_backend.extraction.relationships import GraphWriteSummary

logger = logging.getLogger(__name__)


class GraphIngestionService:
    """Coordinates document/entity extraction writes into Neo4j."""

    def __init__(self, neo4j_client: Neo4jClient | None = None):
        self.settings = get_settings()
        self.neo4j_client = neo4j_client or get_neo4j_client()
        self._text_pipeline: SimpleKGPipeline | None = None
        self._pdf_pipeline: SimpleKGPipeline | None = None
        self._index_ready = False
        self._driver = GraphDatabase.driver(
            self.settings.neo4j_uri,
            auth=(self.settings.neo4j_user, self.settings.neo4j_password),
        )

    def _get_lexical_graph_config(self) -> LexicalGraphConfig:
        return LexicalGraphConfig(
            document_node_label="Document",
            chunk_node_label="Chunk",
            chunk_to_document_relationship_type="FROM_DOCUMENT",
            next_chunk_relationship_type="NEXT_CHUNK",
            node_to_chunk_relationship_type="FROM_CHUNK",
            chunk_id_property="id",
            chunk_index_property="index",
            chunk_text_property="text",
            chunk_embedding_property="embedding",
        )

    def _get_pipeline(self, *, from_pdf: bool) -> SimpleKGPipeline:
        if from_pdf and self._pdf_pipeline is not None:
            return self._pdf_pipeline
        if not from_pdf and self._text_pipeline is not None:
            return self._text_pipeline

        if not self.settings.openai_api_key:
            raise RuntimeError("GraphRAG indexing requires OPENAI_API_KEY")

        llm = OpenAILLM(
            model_name=self.settings.openai_model,
            api_key=self.settings.openai_api_key,
        )
        embedder = OpenAIEmbeddings(
            model=self.settings.graphrag_embedding_model,
            api_key=self.settings.openai_api_key,
        )
        pipeline = SimpleKGPipeline(
            llm=llm,
            driver=self._driver,
            embedder=embedder,
            from_pdf=from_pdf,
            perform_entity_resolution=True,
            lexical_graph_config=self._get_lexical_graph_config(),
            neo4j_database=self.settings.neo4j_database,
        )
        if from_pdf:
            self._pdf_pipeline = pipeline
        else:
            self._text_pipeline = pipeline
        return pipeline

    def _ensure_chunk_vector_index(self) -> None:
        if self._index_ready:
            return

        similarity = (self.settings.graphrag_similarity_fn or "cosine").lower()
        if similarity not in {"cosine", "euclidean"}:
            similarity = "cosine"

        create_vector_index(
            driver=self._driver,
            name=self.settings.graphrag_vector_index_name,
            label="Chunk",
            embedding_property="embedding",
            dimensions=self.settings.graphrag_embedding_dimensions,
            similarity_fn=similarity,
            neo4j_database=self.settings.neo4j_database,
            fail_if_exists=False,
        )
        self._index_ready = True

    @staticmethod
    def _run_async(coro):
        """Run coroutine from sync code path."""
        return asyncio.run(coro)

    def _document_entity_snapshot(self, doc_id: str) -> dict[str, int]:
        """Count document/chunk/entity coverage for post-write observability."""
        with self._driver.session(database=self.settings.neo4j_database) as session:
            record = session.run(
                """
                OPTIONAL MATCH (d:Document {id: $doc_id})
                OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
                OPTIONAL MATCH (d)-[:MENTIONS]->(mentioned:Entity)
                OPTIONAL MATCH (gr:__Entity__)-[:FROM_CHUNK]->(c)
                RETURN count(DISTINCT d) as documents,
                       count(DISTINCT c) as chunks,
                       count(DISTINCT mentioned) as mention_entities,
                       count(DISTINCT gr) as graphrag_entities
                """,
                doc_id=doc_id,
            ).single()

        if not record:
            return {
                "documents": 0,
                "chunks": 0,
                "mention_entities": 0,
                "graphrag_entities": 0,
            }

        return {
            "documents": int(record.get("documents") or 0),
            "chunks": int(record.get("chunks") or 0),
            "mention_entities": int(record.get("mention_entities") or 0),
            "graphrag_entities": int(record.get("graphrag_entities") or 0),
        }

    def upsert_document(
        self,
        *,
        doc_id: str,
        filename: str,
        file_type: str,
        date_extracted: datetime | None,
        created_at: datetime,
    ) -> None:
        """
        No-op for GraphRAG mode.

        Document nodes are created by the GraphRAG pipeline itself.
        """
        _ = doc_id, filename, file_type, date_extracted, created_at

    def extract_and_store_entities(
        self,
        *,
        doc_id: str,
        content: str,
        document_date: datetime | None,
        filename: str | None = None,
        file_type: str | None = None,
        file_path: str | None = None,
        created_at: datetime | None = None,
    ) -> GraphWriteSummary:
        """Extract entities from content and persist them into Neo4j."""
        if not self.settings.openai_api_key:
            raise RuntimeError("GraphRAG indexing requires OPENAI_API_KEY")

        document_metadata: dict[str, str] = {
            "id": doc_id,
            "filename": filename or "",
            "file_type": file_type or "",
            "graph_version": GRAPH_VERSION,
        }
        if document_date is not None:
            document_metadata["date"] = document_date.isoformat()
        if created_at is not None:
            document_metadata["created_at"] = created_at.isoformat()
        if file_path:
            document_metadata["source_path"] = file_path

        use_pdf_pipeline = bool(file_path and str(file_path).lower().endswith(".pdf"))

        # Idempotent re-index for a given document id.
        # Delete all graph data (GraphRAG will recreate the Document node)
        self.neo4j_client.delete_document_graph_data(doc_id)
        self._ensure_chunk_vector_index()
        pipeline = self._get_pipeline(from_pdf=use_pdf_pipeline)
        if use_pdf_pipeline:
            result = self._run_async(
                pipeline.run_async(
                    file_path=file_path,
                    document_metadata=document_metadata,
                )
            )
        else:
            result = self._run_async(
                pipeline.run_async(
                    text=content,
                    file_path=file_path,
                    document_metadata=document_metadata,
                )
            )
        snapshot = self._document_entity_snapshot(doc_id)
        logger.info(
            "graph_ingestion_completed",
            extra={
                "document_id": doc_id,
                "mode": "graphrag",
                "documents": snapshot["documents"],
                "chunks": snapshot["chunks"],
                "graphrag_entities": snapshot["graphrag_entities"],
                "result": str(getattr(result, "result", ""))[:1000],
            },
        )
        if snapshot["graphrag_entities"] == 0:
            logger.warning(
                "graphrag_zero_entities_extracted",
                extra={"document_id": doc_id, **snapshot},
            )
        return GraphWriteSummary(
            entities_seen=snapshot["graphrag_entities"],
            entities_written=snapshot["graphrag_entities"],
        )


_service: GraphIngestionService | None = None


def get_graph_ingestion_service() -> GraphIngestionService:
    """Get or create graph ingestion service singleton."""
    global _service
    if _service is None:
        _service = GraphIngestionService()
    return _service
