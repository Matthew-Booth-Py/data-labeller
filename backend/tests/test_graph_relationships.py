"""Tests for graph canonicalization and idempotent graph writes."""

from __future__ import annotations

from uu_backend.extraction.relationships import (
    build_entity_key,
    canonical_entity_id,
    normalize_entity_name,
    store_entities_and_relationships,
)
from uu_backend.models.entity import Entity, EntityType, Relationship, RelationshipType


class _FakeNeo4jClient:
    def __init__(self):
        self.entities_by_key: dict[str, dict] = {}
        self.mentions: set[tuple[str, str]] = set()
        self.relationships: dict[tuple[str, str, str, str], dict] = {}

    def create_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: EntityType,
        entity_key: str,
        normalized_name: str,
        aliases: list[str] | None = None,
        alias_norms: list[str] | None = None,
        properties=None,
    ) -> str:
        entry = self.entities_by_key.get(entity_key)
        if entry is None:
            self.entities_by_key[entity_key] = {
                "id": entity_id,
                "name": name,
                "type": entity_type,
                "normalized_name": normalized_name,
                "aliases": set(aliases or []),
                "alias_norms": set(alias_norms or []),
                "properties": dict(properties or {}),
            }
            return entity_id

        entry["aliases"].update(aliases or [])
        entry["alias_norms"].update(alias_norms or [])
        return str(entry["id"])

    def link_document_to_entity(
        self,
        doc_id: str,
        entity_id: str,
        properties=None,
        document_date=None,
    ) -> None:
        _ = properties, document_date
        self.mentions.add((doc_id, entity_id))

    def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: RelationshipType,
        properties=None,
    ) -> None:
        props = dict(properties or {})
        doc_id = props.get("document_id", "unknown")
        key = (source_id, target_id, rel_type.value, doc_id)
        self.relationships[key] = props


def _entity(entity_id: str, name: str, entity_type: EntityType, aliases: list[str] | None = None):
    return Entity(
        id=entity_id,
        name=name,
        type=entity_type,
        aliases=aliases or [],
        properties={},
    )


def _relationship(rel_id: str, source_id: str, target_id: str, rel_type: RelationshipType):
    return Relationship(
        id=rel_id,
        source_id=source_id,
        target_id=target_id,
        type=rel_type,
        properties={},
    )


def test_entity_key_is_deterministic_and_type_aware():
    assert normalize_entity_name("  John  Doe ") == "john doe"
    assert build_entity_key(EntityType.PERSON, "John Doe") == build_entity_key(
        EntityType.PERSON, "john  doe"
    )
    assert build_entity_key(EntityType.PERSON, "John Doe") != build_entity_key(
        EntityType.ORGANIZATION, "John Doe"
    )
    assert canonical_entity_id(EntityType.PERSON, "John Doe") == canonical_entity_id(
        EntityType.PERSON, "john doe"
    )


def test_store_entities_relationships_is_idempotent_for_same_document():
    client = _FakeNeo4jClient()

    entities = [
        _entity("e-1", "John Doe", EntityType.PERSON, aliases=["J. Doe"]),
        _entity("e-2", "john   doe", EntityType.PERSON, aliases=["Johnathan Doe"]),
        _entity("e-3", "Acme Corp", EntityType.ORGANIZATION),
    ]
    relationships = [
        _relationship("r-1", "e-2", "e-3", RelationshipType.WORKS_FOR),
    ]

    first = store_entities_and_relationships(
        entities=entities,
        relationships=relationships,
        document_id="doc-1",
        neo4j_client=client,
    )
    second = store_entities_and_relationships(
        entities=entities,
        relationships=relationships,
        document_id="doc-1",
        neo4j_client=client,
    )

    # Same normalized person + same type dedupes, organization stays separate.
    assert len(client.entities_by_key) == 2

    # Reprocessing the same document should not duplicate mention links or doc-scoped edges.
    assert len(client.mentions) == 2
    assert len(client.relationships) == 1

    # Relationship source should map to canonical merged person ID.
    person_key = build_entity_key(EntityType.PERSON, "John Doe")
    canonical_person_id = client.entities_by_key[person_key]["id"]
    rel_key = next(iter(client.relationships.keys()))
    assert rel_key[0] == canonical_person_id

    # Summaries still reflect processed payload size.
    assert first.entities_seen == 3
    assert first.relationships_seen == 1
    assert first.relationships_written == 1
    assert second.entities_seen == 3
    assert second.relationships_written == 1
