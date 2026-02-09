"""Knowledge graph API endpoints."""

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.models.entity import (
    Entity,
    EntityDetailResponse,
    EntityListResponse,
    EntityType,
    GraphData,
)
from uu_backend.models.timeline import TimelineResponse

router = APIRouter()


@router.get("/graph", response_model=GraphData)
async def get_graph(
    entity_types: list[EntityType] | None = Query(
        None,
        description="Filter by entity types",
    ),
    max_nodes: int = Query(
        100,
        ge=1,
        le=500,
        description="Maximum number of nodes to return",
    ),
):
    """
    Get knowledge graph data for visualization.

    Returns nodes (entities) and edges (relationships) suitable for
    graph visualization libraries like Cytoscape.js.
    """
    client = get_neo4j_client()

    try:
        return client.get_graph_data(
            entity_types=entity_types,
            max_nodes=max_nodes,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve graph data: {str(e)}",
        )


@router.get("/graph/entities", response_model=EntityListResponse)
async def list_entities(
    entity_type: EntityType | None = Query(
        None,
        description="Filter by entity type",
    ),
    limit: int = Query(
        100,
        ge=1,
        le=500,
        description="Maximum number of entities to return",
    ),
):
    """
    List all entities in the knowledge graph.

    Optionally filter by entity type (Person, Organization, Location, Event).
    """
    client = get_neo4j_client()

    try:
        entities = client.get_all_entities(
            entity_type=entity_type,
            limit=limit,
        )
        return EntityListResponse(
            entities=entities,
            total=len(entities),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve entities: {str(e)}",
        )


@router.get("/graph/entities/{entity_id}", response_model=EntityDetailResponse)
async def get_entity(entity_id: str):
    """
    Get detailed information about a specific entity.

    Includes related documents and relationships to other entities.
    """
    client = get_neo4j_client()

    try:
        entity = client.get_entity(entity_id)
        if not entity:
            raise HTTPException(
                status_code=404,
                detail=f"Entity not found: {entity_id}",
            )

        related_documents = client.get_entity_documents(entity_id)
        relationships = client.get_entity_relationships(entity_id)

        return EntityDetailResponse(
            entity=entity,
            related_documents=related_documents,
            relationships=relationships,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve entity: {str(e)}",
        )


@router.get("/graph/timeline", response_model=TimelineResponse)
async def get_graph_timeline(
    start_date: date | None = Query(
        None,
        description="Filter documents from this date (inclusive)",
    ),
    end_date: date | None = Query(
        None,
        description="Filter documents until this date (inclusive)",
    ),
):
    """
    Get timeline data from the knowledge graph.

    Returns documents grouped by date, sourced from Neo4j for
    accurate temporal visualization of the knowledge graph.
    """
    client = get_neo4j_client()

    try:
        return client.get_timeline(
            start_date=start_date,
            end_date=end_date,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve timeline: {str(e)}",
        )


@router.get("/graph/stats")
async def get_graph_stats():
    """
    Get knowledge graph statistics.

    Returns counts of documents, entities by type, and relationships.
    """
    client = get_neo4j_client()

    try:
        return client.get_stats()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve graph stats: {str(e)}",
        )
