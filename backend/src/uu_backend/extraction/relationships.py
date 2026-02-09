"""Relationship extraction and management."""

from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.models.entity import Entity, Relationship, RelationshipType


def store_entities_and_relationships(
    entities: list[Entity],
    relationships: list[Relationship],
    document_id: str,
    document_date=None,
) -> None:
    """
    Store extracted entities and relationships in Neo4j.

    Args:
        entities: List of extracted entities
        relationships: List of extracted relationships
        document_id: ID of the source document
        document_date: Date of the document for tracking mentions
    """
    client = get_neo4j_client()

    # Create entity nodes
    for entity in entities:
        client.create_entity(
            entity_id=entity.id,
            name=entity.name,
            entity_type=entity.type,
            properties={
                **entity.properties,
                "aliases": entity.aliases,
            },
        )

        # Link entity to document
        client.link_document_to_entity(
            doc_id=document_id,
            entity_id=entity.id,
        )

        # Update mention tracking
        client.update_entity_mention(
            entity_id=entity.id,
            document_date=document_date,
        )

    # Create relationships between entities
    for rel in relationships:
        client.create_relationship(
            source_id=rel.source_id,
            target_id=rel.target_id,
            rel_type=rel.type,
            properties=rel.properties,
        )


def merge_duplicate_entities(
    new_entities: list[Entity],
    existing_entities: list[Entity],
) -> tuple[list[Entity], dict[str, str]]:
    """
    Merge new entities with existing ones to avoid duplicates.

    Returns:
        - List of truly new entities to create
        - Mapping of new entity IDs to existing entity IDs
    """
    # Build lookup for existing entities by normalized name
    existing_by_name: dict[str, Entity] = {}
    for entity in existing_entities:
        existing_by_name[entity.name.lower()] = entity
        for alias in entity.aliases:
            existing_by_name[alias.lower()] = entity

    new_to_create = []
    id_mapping: dict[str, str] = {}

    for entity in new_entities:
        # Check if this entity already exists
        existing = existing_by_name.get(entity.name.lower())

        if existing:
            # Map new ID to existing ID
            id_mapping[entity.id] = existing.id
        else:
            # Check aliases
            found = False
            for alias in entity.aliases:
                existing = existing_by_name.get(alias.lower())
                if existing:
                    id_mapping[entity.id] = existing.id
                    found = True
                    break

            if not found:
                new_to_create.append(entity)
                # Add to lookup for subsequent entities
                existing_by_name[entity.name.lower()] = entity

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
