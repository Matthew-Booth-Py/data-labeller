"""Relationship extraction and graph-write helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from uu_backend.models.entity import Entity, EntityType, Relationship, RelationshipType

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


@dataclass
class GraphWriteSummary:
    """Summary for a graph write operation."""

    entities_seen: int = 0
    entities_written: int = 0
    relationships_seen: int = 0
    relationships_written: int = 0


def normalize_entity_name(raw_name: str) -> str:
    """Normalize entity names for deterministic identity."""
    normalized = _NON_ALNUM_RE.sub(" ", (raw_name or "").casefold()).strip()
    return re.sub(r"\s+", " ", normalized)


def normalize_aliases(aliases: list[str]) -> tuple[list[str], list[str]]:
    """Normalize aliases while preserving readable originals."""
    canonical_aliases: list[str] = []
    alias_norms: list[str] = []
    seen_norms: set[str] = set()

    for alias in aliases:
        alias_clean = (alias or "").strip()
        if not alias_clean:
            continue

        alias_norm = normalize_entity_name(alias_clean)
        if not alias_norm or alias_norm in seen_norms:
            continue

        seen_norms.add(alias_norm)
        canonical_aliases.append(alias_clean)
        alias_norms.append(alias_norm)

    return canonical_aliases, alias_norms


def build_entity_key(entity_type: EntityType, raw_name: str) -> str:
    """Build canonical key for deduplicating entities."""
    return f"{entity_type.value}|{normalize_entity_name(raw_name)}"


def canonical_entity_id(entity_type: EntityType, raw_name: str) -> str:
    """Build deterministic entity ID from canonical key."""
    return str(uuid5(NAMESPACE_URL, build_entity_key(entity_type, raw_name)))


def store_entities_and_relationships(
    entities: list[Entity],
    relationships: list[Relationship],
    document_id: str,
    document_date=None,
    neo4j_client=None,
) -> GraphWriteSummary:
    """Store extracted entities/relationships - disabled (Neo4j removed)."""
    return GraphWriteSummary(
        entities_seen=len(entities),
        relationships_seen=len(relationships),
        entities_written=0,
        relationships_written=0,
    )


def merge_duplicate_entities(
    new_entities: list[Entity],
    existing_entities: list[Entity],
) -> tuple[list[Entity], dict[str, str]]:
    """Merge new entities with existing entities to avoid duplicates."""
    existing_by_key: dict[str, Entity] = {
        build_entity_key(entity.type, entity.name): entity for entity in existing_entities
    }

    new_to_create = []
    id_mapping: dict[str, str] = {}

    for entity in new_entities:
        entity_key = build_entity_key(entity.type, entity.name)
        existing = existing_by_key.get(entity_key)

        if existing:
            id_mapping[entity.id] = existing.id
            continue

        new_to_create.append(entity)
        existing_by_key[entity_key] = entity

    return new_to_create, id_mapping


def update_relationship_ids(
    relationships: list[Relationship],
    id_mapping: dict[str, str],
) -> list[Relationship]:
    """Update relationship source/target IDs based on entity merging."""
    updated = []

    for rel in relationships:
        new_rel = Relationship(
            id=rel.id,
            source_id=id_mapping.get(rel.source_id, rel.source_id),
            target_id=id_mapping.get(rel.target_id, rel.target_id),
            type=rel.type,
            properties=rel.properties,
            document_ids=rel.document_ids,
        )
        updated.append(new_rel)

    return updated
