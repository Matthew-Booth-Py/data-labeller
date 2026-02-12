"""Tests for Neo4jClient graph query shaping."""

from __future__ import annotations

from uu_backend.database.neo4j_client import Neo4jClient
from uu_backend.models.entity import EntityType


class _FakeResult:
    def __init__(self, records):
        self._records = records

    def __iter__(self):
        return iter(self._records)

    def single(self):
        return self._records[0] if self._records else None


class _FakeSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False

    def run(self, query, **kwargs):
        _ = kwargs
        if "MATCH (n)" in query and "RETURN n, labels(n) as labels" in query:
            return _FakeResult(
                [
                    {
                        "n": {"id": "p-1", "name": "Alice", "type": "Person", "mention_count": 4},
                        "labels": ["Entity", "Person"],
                    },
                    {
                        "n": {
                            "id": "o-1",
                            "name": "Acme",
                            "type": "Organization",
                            "mention_count": 2,
                        },
                        "labels": ["Entity", "Organization"],
                    },
                ]
            )

        if "MATCH (a)-[r]->(b)" in query and "RETURN a.id as source" in query:
            return _FakeResult(
                [
                    {
                        "source": "p-1",
                        "target": "o-1",
                        "rel_type": "WORKS_FOR",
                        "weight": 3,
                        "document_count": 2,
                        "sample_document_ids": ["doc-1", "doc-2"],
                        "max_confidence": 0.92,
                    }
                ]
            )

        return _FakeResult([])


class _FakeDriver:
    def session(self):
        return _FakeSession()

    def verify_connectivity(self):
        return None

    def close(self):
        return None


def test_get_graph_data_aggregates_edge_properties_for_ui():
    client = Neo4jClient(driver=_FakeDriver())

    graph = client.get_graph_data(
        entity_types=[EntityType.PERSON, EntityType.ORGANIZATION],
        max_nodes=50,
    )

    assert len(graph.nodes) == 2
    assert len(graph.edges) == 1

    edge = graph.edges[0]
    assert edge.type == "WORKS_FOR"
    assert edge.properties["weight"] == 3
    assert edge.properties["document_count"] == 2
    assert edge.properties["sample_document_ids"] == ["doc-1", "doc-2"]
    assert edge.properties["max_confidence"] == 0.92
    assert edge.properties["graph_version"] == "v1"


class _DeleteFakeSession:
    def __init__(self):
        self.queries: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False

    def run(self, query, **kwargs):
        _ = kwargs
        self.queries.append(query)

        if "RETURN count(DISTINCT d) as docs" in query:
            return _FakeResult([{"docs": 0, "entity_ids": []}])

        if "WHERE r.document_id = $id" in query:
            return _FakeResult([{"rel_count": 2}])

        if "MATCH (e:Entity)" in query and "RETURN pruned" in query:
            return _FakeResult([{"pruned": 1}])

        if "MATCH (e:__Entity__)" in query and "RETURN pruned" in query:
            return _FakeResult([{"pruned": 0}])

        return _FakeResult([])


class _DeleteFakeDriver:
    def __init__(self):
        self.session_instance = _DeleteFakeSession()

    def session(self):
        return self.session_instance

    def verify_connectivity(self):
        return None

    def close(self):
        return None


def test_delete_document_graph_data_cleans_doc_scoped_relationships_without_document_node():
    driver = _DeleteFakeDriver()
    client = Neo4jClient(driver=driver)

    summary = client.delete_document_graph_data("doc-missing")

    assert summary["deleted_documents"] == 0
    assert summary["deleted_document_relationships"] == 2
    assert summary["pruned_entities"] == 1
    assert not any("DETACH DELETE d" in query for query in driver.session_instance.queries)


class _ReconcileSession:
    def __init__(self, stale_ids):
        self.stale_ids = stale_ids

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False

    def run(self, query, **kwargs):
        _ = kwargs
        if "RETURN collect(d.id) as stale_ids" in query:
            return _FakeResult([{"stale_ids": self.stale_ids}])
        return _FakeResult([])


class _ReconcileDriver:
    def __init__(self, stale_ids):
        self.session_instance = _ReconcileSession(stale_ids)

    def session(self):
        return self.session_instance

    def verify_connectivity(self):
        return None

    def close(self):
        return None


class _RecordingReconcileClient(Neo4jClient):
    def __init__(self, stale_ids):
        super().__init__(driver=_ReconcileDriver(stale_ids))
        self.deleted_ids: list[str] = []

    def delete_document_graph_data(self, doc_id: str) -> dict[str, int]:
        self.deleted_ids.append(doc_id)
        return {
            "deleted_documents": 1,
            "deleted_document_relationships": 2,
            "pruned_entities": 3,
        }


def test_reconcile_documents_removes_stale_graph_docs():
    client = _RecordingReconcileClient(["stale-1", "stale-2"])

    summary = client.reconcile_documents(valid_document_ids=["doc-1", "doc-2"])

    assert client.deleted_ids == ["stale-1", "stale-2"]
    assert summary["stale_documents_found"] == 2
    assert summary["deleted_documents"] == 2
    assert summary["deleted_document_relationships"] == 4
    assert summary["pruned_entities"] == 6


class _ChunkIndexedSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        _ = exc_type, exc, tb
        return False

    def run(self, query, **kwargs):
        _ = kwargs
        if "MATCH (d:Document)<-[:FROM_DOCUMENT]-(:Chunk)" in query:
            return _FakeResult([{"id": "doc-1"}, {"id": "doc-2"}])
        return _FakeResult([])


class _ChunkIndexedDriver:
    def session(self):
        return _ChunkIndexedSession()

    def verify_connectivity(self):
        return None

    def close(self):
        return None


def test_get_document_ids_with_chunks_returns_distinct_document_ids():
    client = Neo4jClient(driver=_ChunkIndexedDriver())

    indexed_ids = client.get_document_ids_with_chunks()

    assert indexed_ids == {"doc-1", "doc-2"}
