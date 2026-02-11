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
        if "MATCH (n:Entity)" in query:
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

        if "MATCH (a:Entity)-[r]->(b:Entity)" in query:
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
