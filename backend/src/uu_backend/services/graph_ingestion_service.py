"""Graph ingestion orchestration for Neo4j writes."""

from __future__ import annotations

import logging
from datetime import datetime

from uu_backend.database.neo4j_client import Neo4jClient, get_neo4j_client
from uu_backend.extraction.entities import extract_entities
from uu_backend.extraction.relationships import GraphWriteSummary, store_entities_and_relationships

logger = logging.getLogger(__name__)


class GraphIngestionService:
    """Coordinates document/entity extraction writes into Neo4j."""

    def __init__(self, neo4j_client: Neo4jClient | None = None):
        self.neo4j_client = neo4j_client or get_neo4j_client()

    def upsert_document(
        self,
        *,
        doc_id: str,
        filename: str,
        file_type: str,
        date_extracted: datetime | None,
        created_at: datetime,
    ) -> None:
        """Create or update the document node in Neo4j."""
        self.neo4j_client.create_document(
            doc_id=doc_id,
            filename=filename,
            file_type=file_type,
            date_extracted=date_extracted,
            created_at=created_at,
        )

    def extract_and_store_entities(
        self,
        *,
        doc_id: str,
        content: str,
        document_date: datetime | None,
    ) -> GraphWriteSummary:
        """Extract entities from content and persist them into Neo4j."""
        extracted = extract_entities(content, doc_id)
        if not extracted.entities and not extracted.relationships:
            return GraphWriteSummary()

        summary = store_entities_and_relationships(
            entities=extracted.entities,
            relationships=extracted.relationships,
            document_id=doc_id,
            document_date=document_date,
            neo4j_client=self.neo4j_client,
        )

        logger.info(
            "graph_ingestion_completed",
            extra={
                "document_id": doc_id,
                "entities_seen": summary.entities_seen,
                "entities_written": summary.entities_written,
                "relationships_seen": summary.relationships_seen,
                "relationships_written": summary.relationships_written,
            },
        )
        return summary


_service: GraphIngestionService | None = None


def get_graph_ingestion_service() -> GraphIngestionService:
    """Get or create graph ingestion service singleton."""
    global _service
    if _service is None:
        _service = GraphIngestionService()
    return _service
