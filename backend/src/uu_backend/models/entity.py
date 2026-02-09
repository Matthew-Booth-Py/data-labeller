"""Entity models for knowledge graph."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EntityType(str, Enum):
    """Types of entities that can be extracted."""

    PERSON = "Person"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    EVENT = "Event"


class RelationshipType(str, Enum):
    """Types of relationships between entities."""

    MENTIONS = "MENTIONS"  # Document mentions entity
    COMMUNICATED_WITH = "COMMUNICATED_WITH"  # Person to Person
    WORKS_FOR = "WORKS_FOR"  # Person to Organization
    ATTENDED = "ATTENDED"  # Person to Event
    LOCATED_AT = "LOCATED_AT"  # Entity at Location
    INVOLVED_IN = "INVOLVED_IN"  # Entity involved in Event
    OCCURRED_AT = "OCCURRED_AT"  # Event at Location


class Entity(BaseModel):
    """Base entity model."""

    id: str
    name: str
    type: EntityType
    aliases: list[str] = Field(default_factory=list)
    properties: dict[str, Any] = Field(default_factory=dict)
    mention_count: int = 0
    first_mentioned: datetime | None = None
    last_mentioned: datetime | None = None


class Person(Entity):
    """Person entity."""

    type: EntityType = EntityType.PERSON
    role: str | None = None
    title: str | None = None


class Organization(Entity):
    """Organization entity."""

    type: EntityType = EntityType.ORGANIZATION
    org_type: str | None = None  # company, nonprofit, government, etc.


class Location(Entity):
    """Location entity."""

    type: EntityType = EntityType.LOCATION
    location_type: str | None = None  # city, country, address, etc.
    coordinates: tuple[float, float] | None = None


class Event(Entity):
    """Event entity."""

    type: EntityType = EntityType.EVENT
    date: datetime | None = None
    event_type: str | None = None  # meeting, communication, etc.
    description: str | None = None


class Relationship(BaseModel):
    """Relationship between entities."""

    id: str
    source_id: str
    target_id: str
    type: RelationshipType
    properties: dict[str, Any] = Field(default_factory=dict)
    weight: float = 1.0
    document_ids: list[str] = Field(default_factory=list)


class GraphNode(BaseModel):
    """Node representation for graph visualization."""

    id: str
    label: str
    type: EntityType
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Edge representation for graph visualization."""

    source: str
    target: str
    type: RelationshipType
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphData(BaseModel):
    """Complete graph data for visualization."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class EntityListResponse(BaseModel):
    """Response containing list of entities."""

    entities: list[Entity]
    total: int


class EntityDetailResponse(BaseModel):
    """Detailed entity response with related documents."""

    entity: Entity
    related_documents: list[dict[str, Any]]
    relationships: list[Relationship]
