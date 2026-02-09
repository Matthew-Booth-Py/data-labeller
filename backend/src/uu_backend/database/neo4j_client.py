"""Neo4j client for knowledge graph operations."""

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from uu_backend.config import get_settings
from uu_backend.models.entity import (
    Entity,
    EntityType,
    GraphData,
    GraphEdge,
    GraphNode,
    Relationship,
    RelationshipType,
)
from uu_backend.models.timeline import (
    DateRange,
    TimelineDocument,
    TimelineEntry,
    TimelineResponse,
)


class Neo4jClient:
    """Client for Neo4j graph database operations."""

    def __init__(self):
        """Initialize Neo4j connection."""
        settings = get_settings()
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        self._initialized = False

    def close(self):
        """Close the driver connection."""
        self._driver.close()

    def verify_connectivity(self) -> bool:
        """Verify connection to Neo4j."""
        try:
            self._driver.verify_connectivity()
            return True
        except ServiceUnavailable:
            return False

    def initialize_schema(self):
        """Create indexes and constraints."""
        if self._initialized:
            return

        with self._driver.session() as session:
            # Create constraints for unique IDs
            session.run(
                "CREATE CONSTRAINT document_id IF NOT EXISTS "
                "FOR (d:Document) REQUIRE d.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT person_id IF NOT EXISTS "
                "FOR (p:Person) REQUIRE p.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT organization_id IF NOT EXISTS "
                "FOR (o:Organization) REQUIRE o.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT location_id IF NOT EXISTS "
                "FOR (l:Location) REQUIRE l.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT event_id IF NOT EXISTS "
                "FOR (e:Event) REQUIRE e.id IS UNIQUE"
            )

            # Create indexes for common queries
            session.run(
                "CREATE INDEX document_date IF NOT EXISTS "
                "FOR (d:Document) ON (d.date)"
            )
            session.run(
                "CREATE INDEX entity_name IF NOT EXISTS "
                "FOR (n:Entity) ON (n.name)"
            )

        self._initialized = True

    # =========================================================================
    # Document Operations
    # =========================================================================

    def create_document(
        self,
        doc_id: str,
        filename: str,
        file_type: str,
        date_extracted: datetime | None = None,
        created_at: datetime | None = None,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create a document node."""
        with self._driver.session() as session:
            props = {
                "id": doc_id,
                "filename": filename,
                "file_type": file_type,
                "created_at": (created_at or datetime.utcnow()).isoformat(),
            }
            if date_extracted:
                props["date"] = date_extracted.isoformat()
            if properties:
                props.update(properties)

            session.run(
                """
                MERGE (d:Document {id: $id})
                SET d += $props
                """,
                id=doc_id,
                props=props,
            )

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        """Get a document by ID."""
        with self._driver.session() as session:
            result = session.run(
                "MATCH (d:Document {id: $id}) RETURN d",
                id=doc_id,
            )
            record = result.single()
            if record:
                return dict(record["d"])
            return None

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document and its relationships."""
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (d:Document {id: $id})
                DETACH DELETE d
                RETURN count(d) as deleted
                """,
                id=doc_id,
            )
            record = result.single()
            return record["deleted"] > 0 if record else False

    # =========================================================================
    # Entity Operations
    # =========================================================================

    def create_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: EntityType,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create an entity node."""
        with self._driver.session() as session:
            props = {
                "id": entity_id,
                "name": name,
                "created_at": datetime.utcnow().isoformat(),
            }
            if properties:
                props.update(properties)

            # Use the entity type as the label
            label = entity_type.value
            session.run(
                f"""
                MERGE (e:{label} {{id: $id}})
                SET e += $props
                SET e:Entity
                """,
                id=entity_id,
                props=props,
            )

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID."""
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity {id: $id})
                RETURN e, labels(e) as labels
                """,
                id=entity_id,
            )
            record = result.single()
            if not record:
                return None

            node = dict(record["e"])
            labels = record["labels"]

            # Determine entity type from labels
            entity_type = EntityType.PERSON
            for label in labels:
                if label in [et.value for et in EntityType]:
                    entity_type = EntityType(label)
                    break

            return Entity(
                id=node["id"],
                name=node.get("name", ""),
                type=entity_type,
                aliases=node.get("aliases", []),
                properties=node,
            )

    def get_all_entities(
        self,
        entity_type: EntityType | None = None,
        limit: int = 100,
    ) -> list[Entity]:
        """Get all entities, optionally filtered by type."""
        with self._driver.session() as session:
            if entity_type:
                query = f"""
                    MATCH (e:{entity_type.value})
                    RETURN e, labels(e) as labels
                    LIMIT $limit
                """
            else:
                query = """
                    MATCH (e:Entity)
                    RETURN e, labels(e) as labels
                    LIMIT $limit
                """

            result = session.run(query, limit=limit)
            entities = []

            for record in result:
                node = dict(record["e"])
                labels = record["labels"]

                # Determine entity type from labels
                etype = EntityType.PERSON
                for label in labels:
                    if label in [et.value for et in EntityType]:
                        etype = EntityType(label)
                        break

                entities.append(
                    Entity(
                        id=node["id"],
                        name=node.get("name", ""),
                        type=etype,
                        aliases=node.get("aliases", []),
                        properties=node,
                    )
                )

            return entities

    def update_entity_mention(
        self,
        entity_id: str,
        document_date: datetime | None = None,
    ) -> None:
        """Update entity mention count and dates."""
        with self._driver.session() as session:
            if document_date:
                session.run(
                    """
                    MATCH (e:Entity {id: $id})
                    SET e.mention_count = COALESCE(e.mention_count, 0) + 1,
                        e.first_mentioned = CASE 
                            WHEN e.first_mentioned IS NULL OR e.first_mentioned > $date 
                            THEN $date 
                            ELSE e.first_mentioned 
                        END,
                        e.last_mentioned = CASE 
                            WHEN e.last_mentioned IS NULL OR e.last_mentioned < $date 
                            THEN $date 
                            ELSE e.last_mentioned 
                        END
                    """,
                    id=entity_id,
                    date=document_date.isoformat(),
                )
            else:
                session.run(
                    """
                    MATCH (e:Entity {id: $id})
                    SET e.mention_count = COALESCE(e.mention_count, 0) + 1
                    """,
                    id=entity_id,
                )

    # =========================================================================
    # Relationship Operations
    # =========================================================================

    def create_relationship(
        self,
        source_id: str,
        target_id: str,
        rel_type: RelationshipType,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Create a relationship between two nodes."""
        with self._driver.session() as session:
            props = properties or {}
            props["created_at"] = datetime.utcnow().isoformat()

            # Dynamic relationship type
            query = f"""
                MATCH (a {{id: $source_id}})
                MATCH (b {{id: $target_id}})
                MERGE (a)-[r:{rel_type.value}]->(b)
                SET r += $props
            """
            session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                props=props,
            )

    def link_document_to_entity(
        self,
        doc_id: str,
        entity_id: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Link a document to an entity via MENTIONS relationship."""
        self.create_relationship(
            doc_id,
            entity_id,
            RelationshipType.MENTIONS,
            properties,
        )

    def get_entity_relationships(
        self,
        entity_id: str,
    ) -> list[Relationship]:
        """Get all relationships for an entity."""
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (e:Entity {id: $id})-[r]-(other)
                RETURN type(r) as rel_type, 
                       startNode(r).id as source_id,
                       endNode(r).id as target_id,
                       properties(r) as props,
                       id(r) as rel_id
                """,
                id=entity_id,
            )

            relationships = []
            for record in result:
                try:
                    rel_type = RelationshipType(record["rel_type"])
                except ValueError:
                    continue

                relationships.append(
                    Relationship(
                        id=str(record["rel_id"]),
                        source_id=record["source_id"],
                        target_id=record["target_id"],
                        type=rel_type,
                        properties=record["props"] or {},
                    )
                )

            return relationships

    def get_entity_documents(
        self,
        entity_id: str,
    ) -> list[dict[str, Any]]:
        """Get all documents that mention an entity."""
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (d:Document)-[:MENTIONS]->(e:Entity {id: $id})
                RETURN d
                ORDER BY d.date DESC
                """,
                id=entity_id,
            )

            return [dict(record["d"]) for record in result]

    # =========================================================================
    # Graph Queries
    # =========================================================================

    def get_graph_data(
        self,
        entity_types: list[EntityType] | None = None,
        max_nodes: int = 100,
    ) -> GraphData:
        """Get graph data for visualization."""
        with self._driver.session() as session:
            # Build query based on filters
            if entity_types:
                labels = ":".join([et.value for et in entity_types])
                node_query = f"MATCH (n:{labels}) RETURN n, labels(n) as labels LIMIT $limit"
            else:
                node_query = "MATCH (n:Entity) RETURN n, labels(n) as labels LIMIT $limit"

            # Get nodes
            result = session.run(node_query, limit=max_nodes)
            nodes = []
            node_ids = set()

            for record in result:
                node = dict(record["n"])
                labels = record["labels"]

                # Determine entity type
                etype = EntityType.PERSON
                for label in labels:
                    if label in [et.value for et in EntityType]:
                        etype = EntityType(label)
                        break

                nodes.append(
                    GraphNode(
                        id=node["id"],
                        label=node.get("name", node["id"]),
                        type=etype,
                        properties=node,
                    )
                )
                node_ids.add(node["id"])

            # Get edges between these nodes
            if node_ids:
                edge_result = session.run(
                    """
                    MATCH (a)-[r]->(b)
                    WHERE a.id IN $ids AND b.id IN $ids
                    RETURN a.id as source, b.id as target, type(r) as rel_type, properties(r) as props
                    """,
                    ids=list(node_ids),
                )

                edges = []
                for record in edge_result:
                    try:
                        rel_type = RelationshipType(record["rel_type"])
                    except ValueError:
                        continue

                    edges.append(
                        GraphEdge(
                            source=record["source"],
                            target=record["target"],
                            type=rel_type,
                            properties=record["props"] or {},
                        )
                    )
            else:
                edges = []

            return GraphData(nodes=nodes, edges=edges)

    # =========================================================================
    # Timeline Queries
    # =========================================================================

    def get_timeline(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TimelineResponse:
        """Get documents grouped by date for timeline visualization."""
        with self._driver.session() as session:
            # Build date filter
            where_clauses = ["d.date IS NOT NULL"]
            params: dict[str, Any] = {}

            if start_date:
                where_clauses.append("d.date >= $start_date")
                params["start_date"] = start_date.isoformat()
            if end_date:
                where_clauses.append("d.date <= $end_date")
                params["end_date"] = end_date.isoformat()

            where_clause = " AND ".join(where_clauses)

            result = session.run(
                f"""
                MATCH (d:Document)
                WHERE {where_clause}
                RETURN d
                ORDER BY d.date
                """,
                **params,
            )

            # Group by date
            by_date: dict[date, list[TimelineDocument]] = defaultdict(list)
            earliest: date | None = None
            latest: date | None = None

            for record in result:
                doc = dict(record["d"])
                try:
                    doc_date = datetime.fromisoformat(doc["date"]).date()
                except (ValueError, KeyError):
                    continue

                if earliest is None or doc_date < earliest:
                    earliest = doc_date
                if latest is None or doc_date > latest:
                    latest = doc_date

                by_date[doc_date].append(
                    TimelineDocument(
                        id=doc["id"],
                        filename=doc.get("filename", ""),
                        file_type=doc.get("file_type", ""),
                        title=doc.get("filename", ""),
                    )
                )

            # Build timeline entries
            timeline = [
                TimelineEntry(
                    date=d,
                    document_count=len(docs),
                    documents=docs,
                )
                for d, docs in sorted(by_date.items())
            ]

            return TimelineResponse(
                timeline=timeline,
                date_range=DateRange(earliest=earliest, latest=latest),
                total_documents=sum(len(docs) for docs in by_date.values()),
            )

    # =========================================================================
    # Stats
    # =========================================================================

    def get_stats(self) -> dict[str, int]:
        """Get graph statistics."""
        with self._driver.session() as session:
            result = session.run(
                """
                MATCH (d:Document) WITH count(d) as docs
                MATCH (p:Person) WITH docs, count(p) as persons
                MATCH (o:Organization) WITH docs, persons, count(o) as orgs
                MATCH (l:Location) WITH docs, persons, orgs, count(l) as locations
                MATCH (e:Event) WITH docs, persons, orgs, locations, count(e) as events
                MATCH ()-[r]->() WITH docs, persons, orgs, locations, events, count(r) as rels
                RETURN docs, persons, orgs, locations, events, rels
                """
            )
            record = result.single()
            if record:
                return {
                    "documents": record["docs"],
                    "persons": record["persons"],
                    "organizations": record["orgs"],
                    "locations": record["locations"],
                    "events": record["events"],
                    "relationships": record["rels"],
                }
            return {
                "documents": 0,
                "persons": 0,
                "organizations": 0,
                "locations": 0,
                "events": 0,
                "relationships": 0,
            }


# Module-level instance
_client: Neo4jClient | None = None


def get_neo4j_client() -> Neo4jClient:
    """Get or create the Neo4j client instance."""
    global _client
    if _client is None:
        _client = Neo4jClient()
        _client.initialize_schema()
    return _client
