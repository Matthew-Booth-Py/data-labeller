"""Tests for Neo4j indexing Celery tasks."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from uu_backend.extraction.relationships import GraphWriteSummary
from uu_backend.tasks import neo4j_tasks


class _FakeVectorStore:
    def __init__(self, document):
        self._document = document

    def get_document(self, document_id: str):
        _ = document_id
        return self._document


class _FakeNeo4jClient:
    def __init__(self, event_log: list[str]):
        self.event_log = event_log
        self.created_documents: list[dict] = []
        self.deleted_doc_ids: list[str] = []

    def create_document(
        self,
        doc_id: str,
        filename: str,
        file_type: str,
        date_extracted: datetime | None = None,
        created_at: datetime | None = None,
        properties: dict | None = None,
    ) -> None:
        self.event_log.append("create_document")
        self.created_documents.append(
            {
                "doc_id": doc_id,
                "filename": filename,
                "file_type": file_type,
                "date_extracted": date_extracted,
                "created_at": created_at,
                "properties": properties,
            }
        )

    def delete_document_graph_data(self, doc_id: str) -> None:
        self.deleted_doc_ids.append(doc_id)


class _FakeGraphIngestionService:
    def __init__(self, event_log: list[str]):
        self.event_log = event_log
        self.calls: list[dict] = []

    def extract_and_store_entities(self, **kwargs):
        self.event_log.append("graphrag_extract")
        self.calls.append(kwargs)
        return GraphWriteSummary(entities_written=7)


def test_index_document_task_indexes_graphrag_chunks_and_entities(monkeypatch):
    event_log: list[str] = []
    document = SimpleNamespace(
        id="doc-1",
        filename="claim_form_auto_2024.pdf",
        file_type="pdf",
        content="TOTAL ESTIMATE: $3,950.00",
        date_extracted=None,
        created_at=datetime(2024, 1, 18, 12, 0, 0),
    )
    graph_service = _FakeGraphIngestionService(event_log)
    neo4j_client = _FakeNeo4jClient(event_log)

    monkeypatch.setattr(neo4j_tasks, "get_vector_store", lambda: _FakeVectorStore(document))
    monkeypatch.setattr(neo4j_tasks, "get_graph_ingestion_service", lambda: graph_service)
    monkeypatch.setattr(neo4j_tasks, "get_neo4j_client", lambda: neo4j_client)
    monkeypatch.setattr(
        neo4j_tasks,
        "_resolve_original_file_path",
        lambda document_id, file_type: f"/tmp/{document_id}.{file_type}",
    )

    def _fake_extract_entities(content: str, document_id: str):
        event_log.append("entity_extract")
        _ = content, document_id
        return SimpleNamespace(entities=["entity"], relationships=["relationship"])

    def _fake_store_entities_and_relationships(
        entities,
        relationships,
        document_id: str,
        document_date=None,
        neo4j_client=None,
    ):
        event_log.append("store_entity_graph")
        _ = entities, relationships, document_id, document_date, neo4j_client
        return None

    monkeypatch.setattr(neo4j_tasks, "extract_entities", _fake_extract_entities)
    monkeypatch.setattr(
        neo4j_tasks,
        "store_entities_and_relationships",
        _fake_store_entities_and_relationships,
    )

    result = neo4j_tasks.index_document_in_neo4j_task.run("doc-1")

    assert result["status"] == "indexed"
    assert result["document_id"] == "doc-1"
    assert result["graphrag_entities"] == 7
    assert result["entities"] == 1
    assert result["relationships"] == 1

    assert event_log == [
        "graphrag_extract",
        "entity_extract",
        "create_document",
        "store_entity_graph",
    ]
    assert len(graph_service.calls) == 1
    assert graph_service.calls[0]["doc_id"] == "doc-1"


def test_index_document_task_returns_missing_document_without_indexing(monkeypatch):
    monkeypatch.setattr(neo4j_tasks, "get_vector_store", lambda: _FakeVectorStore(None))

    result = neo4j_tasks.index_document_in_neo4j_task.run("missing-doc")

    assert result == {"status": "missing_document", "document_id": "missing-doc"}
