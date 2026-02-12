"""Entity extraction from document content."""

import logging
import uuid
from typing import Any

from uu_backend.llm.openai_client import get_openai_client
from uu_backend.llm.prompts import (
    ENTITY_EXTRACTION_PROMPT,
    ENTITY_EXTRACTION_SYSTEM,
)
from uu_backend.models.entity import (
    Entity,
    EntityType,
    Relationship,
    RelationshipType,
)

logger = logging.getLogger(__name__)


class ExtractedData:
    """Container for extracted entities and relationships."""

    def __init__(
        self,
        entities: list[Entity],
        relationships: list[Relationship],
    ):
        self.entities = entities
        self.relationships = relationships


class EntityExtractor:
    """Extract entities from document content using LLM."""

    def __init__(self):
        """Initialize the entity extractor."""
        self._client = get_openai_client()

    def extract(self, content: str, document_id: str) -> ExtractedData:
        """
        Extract entities and relationships from content.

        Args:
            content: The document text to extract from
            document_id: ID of the source document

        Returns:
            ExtractedData containing entities and relationships
        """
        # Check if OpenAI is available
        if not self._client.is_available():
            raise RuntimeError("OpenAI client is not available for entity extraction")

        # Truncate content if too long (to fit in context window)
        max_chars = 15000
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[Content truncated...]"

        # Extract using LLM
        prompt = ENTITY_EXTRACTION_PROMPT.format(content=content)

        try:
            result = self._client.complete_json(
                prompt=prompt,
                system_prompt=ENTITY_EXTRACTION_SYSTEM,
            )
        except Exception:
            logger.exception("Entity extraction request failed for document %s", document_id)
            raise

        # Validate payload shape so malformed model output cannot silently pass.
        if not isinstance(result, dict):
            raise ValueError("Entity extraction response is not a JSON object")
        if "entities" not in result or not isinstance(result.get("entities"), list):
            raise ValueError("Entity extraction response missing list field 'entities'")
        if "relationships" not in result or not isinstance(result.get("relationships"), list):
            raise ValueError("Entity extraction response missing list field 'relationships'")

        # Parse entities
        entities = self._parse_entities(result.get("entities", []))

        # Parse relationships
        relationships = self._parse_relationships(
            result.get("relationships", []),
            entities,
            document_id,
        )

        return ExtractedData(entities=entities, relationships=relationships)

    def _parse_entities(self, raw_entities: list[dict[str, Any]]) -> list[Entity]:
        """Parse raw entity data into Entity objects."""
        entities = []
        seen_names: set[str] = set()

        for raw in raw_entities:
            name = raw.get("name", "").strip()
            if not name or name.lower() in seen_names:
                continue

            seen_names.add(name.lower())

            # Determine entity type
            type_str = raw.get("type", "Person")
            try:
                entity_type = EntityType(type_str)
            except ValueError:
                entity_type = EntityType.PERSON

            # Build properties
            properties: dict[str, Any] = {}
            if raw.get("context"):
                properties["context"] = raw["context"]
            if raw.get("role"):
                properties["role"] = raw["role"]
            if raw.get("date"):
                properties["date"] = raw["date"]

            entities.append(
                Entity(
                    id=str(uuid.uuid4()),
                    name=name,
                    type=entity_type,
                    aliases=raw.get("aliases", []),
                    properties=properties,
                )
            )

        return entities

    def _parse_relationships(
        self,
        raw_relationships: list[dict[str, Any]],
        entities: list[Entity],
        document_id: str,
    ) -> list[Relationship]:
        """Parse raw relationship data into Relationship objects."""
        # Build name to entity ID mapping
        name_to_id: dict[str, str] = {}
        for entity in entities:
            name_to_id[entity.name.lower()] = entity.id
            for alias in entity.aliases:
                name_to_id[alias.lower()] = entity.id

        relationships = []

        for raw in raw_relationships:
            source_name = raw.get("source", "").strip().lower()
            target_name = raw.get("target", "").strip().lower()

            source_id = name_to_id.get(source_name)
            target_id = name_to_id.get(target_name)

            if not source_id or not target_id:
                continue

            # Determine relationship type
            type_str = raw.get("type", "")
            try:
                rel_type = RelationshipType(type_str)
            except ValueError:
                continue

            # Build properties
            properties: dict[str, Any] = {
                "document_id": document_id,
            }
            if raw.get("context"):
                properties["context"] = raw["context"]
            if raw.get("confidence"):
                properties["confidence"] = raw["confidence"]
            if raw.get("evidence"):
                properties["evidence"] = raw["evidence"]

            relationships.append(
                Relationship(
                    id=str(uuid.uuid4()),
                    source_id=source_id,
                    target_id=target_id,
                    type=rel_type,
                    properties=properties,
                    document_ids=[document_id],
                )
            )

        return relationships


# Module-level instance
_extractor: EntityExtractor | None = None


def get_entity_extractor() -> EntityExtractor:
    """Get or create the EntityExtractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = EntityExtractor()
    return _extractor


def extract_entities(content: str, document_id: str) -> ExtractedData:
    """Convenience function to extract entities from content."""
    return get_entity_extractor().extract(content, document_id)
