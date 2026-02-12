"""Neo4j client for knowledge graph operations."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable

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

GRAPH_VERSION = "v1"


class Neo4jClient:
    """Client for Neo4j graph database operations."""

    def __init__(self, driver: Any | None = None):
        """Initialize Neo4j connection."""
        settings = get_settings()
        self._database = settings.neo4j_database
        if driver is not None:
            self._driver = driver
        else:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
        self._initialized = False

    def _session(self):
        """Open a Neo4j session honoring configured database when supported."""
        if self._database:
            try:
                return self._driver.session(database=self._database)
            except TypeError:
                # Test doubles or older driver shims may not accept `database`.
                pass
        return self._driver.session()

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

        with self._session() as session:
            session.run(
                "CREATE CONSTRAINT document_id IF NOT EXISTS "
                "FOR (d:Document) REQUIRE d.id IS UNIQUE"
            )
            session.run(
                "CREATE CONSTRAINT entity_key IF NOT EXISTS "
                "FOR (e:Entity) REQUIRE e.key IS UNIQUE"
            )
            session.run(
                "CREATE INDEX document_date IF NOT EXISTS "
                "FOR (d:Document) ON (d.date)"
            )
            session.run(
                "CREATE INDEX entity_name IF NOT EXISTS "
                "FOR (e:Entity) ON (e.name)"
            )
            session.run(
                "CREATE INDEX entity_normalized_name IF NOT EXISTS "
                "FOR (e:Entity) ON (e.normalized_name)"
            )
            session.run(
                "CREATE INDEX entity_type IF NOT EXISTS "
                "FOR (e:Entity) ON (e.type)"
            )

            # Relationship property indexes are available in newer Neo4j versions.
            try:
                session.run(
                    "CREATE INDEX rel_document_id IF NOT EXISTS "
                    "FOR ()-[r]-() ON (r.document_id)"
                )
            except Neo4jError:
                pass

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
        """Create or update a document node."""
        with self._session() as session:
            now_iso = (created_at or datetime.utcnow()).isoformat()
            props: dict[str, Any] = {
                "id": doc_id,
                "filename": filename,
                "file_type": file_type,
                "created_at": now_iso,
                "graph_version": GRAPH_VERSION,
            }
            if date_extracted:
                props["date"] = date_extracted.isoformat()
            if properties:
                props.update(properties)

            session.run(
                """
                MERGE (d:Document {id: $id})
                ON CREATE SET d.created_at = $created_at
                SET d += $props
                """,
                id=doc_id,
                created_at=now_iso,
                props=props,
            )

    def get_document(self, doc_id: str) -> dict[str, Any] | None:
        """Get a document by ID."""
        with self._session() as session:
            result = session.run(
                "MATCH (d:Document {id: $id}) RETURN d",
                id=doc_id,
            )
            record = result.single()
            if record:
                return dict(record["d"])
            return None

    def get_all_document_ids(self) -> set[str]:
        """Get all document IDs currently stored in Neo4j."""
        with self._session() as session:
            result = session.run("MATCH (d:Document) RETURN d.id as id")
            return {record["id"] for record in result if record.get("id")}

    def get_document_ids_with_chunks(self) -> set[str]:
        """Get document IDs that have at least one graph chunk linked for Q&A retrieval."""
        with self._session() as session:
            result = session.run(
                """
                MATCH (d:Document)<-[:FROM_DOCUMENT]-(:Chunk)
                RETURN DISTINCT d.id as id
                """
            )
            return {record["id"] for record in result if record.get("id")}

    def delete_document(self, doc_id: str) -> bool:
        """Delete a document and related graph data."""
        summary = self.delete_document_graph_data(doc_id)
        return summary["deleted_documents"] > 0

    def delete_document_graph_data(self, doc_id: str) -> dict[str, int]:
        """Delete one document and graph data derived from it."""
        with self._session() as session:
            record = session.run(
                """
                MATCH (d:Document {id: $id})
                OPTIONAL MATCH (d)-[:MENTIONS]->(e:Entity)
                OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
                RETURN count(DISTINCT d) as docs,
                       collect(DISTINCT e.id) as entity_ids,
                       collect(DISTINCT elementId(c)) as chunk_ids
                """,
                id=doc_id,
            ).single()

            doc_count = int(record["docs"] or 0) if record else 0
            entity_ids = [
                eid for eid in ((record.get("entity_ids") if record else []) or []) if eid
            ]
            chunk_ids = [cid for cid in ((record.get("chunk_ids") if record else []) or []) if cid]

            rel_record = session.run(
                """
                MATCH ()-[r]->()
                WHERE r.document_id = $id
                WITH collect(r) as rels, size(collect(r)) as rel_count
                FOREACH (rel IN rels | DELETE rel)
                RETURN rel_count
                """,
                id=doc_id,
            ).single()
            deleted_doc_rels = int(rel_record["rel_count"] or 0) if rel_record else 0

            deleted_chunks = 0
            if chunk_ids:
                chunk_record = session.run(
                    """
                    UNWIND $chunk_ids AS chunk_id
                    MATCH (c:Chunk)
                    WHERE elementId(c) = chunk_id
                    WITH collect(c) as chunks, size(collect(c)) as chunk_count
                    FOREACH (chunk IN chunks | DETACH DELETE chunk)
                    RETURN chunk_count
                    """,
                    chunk_ids=chunk_ids,
                ).single()
                deleted_chunks = int(chunk_record["chunk_count"] or 0) if chunk_record else 0

            if doc_count > 0:
                session.run(
                    """
                    MATCH (d:Document {id: $id})
                    DETACH DELETE d
                    """,
                    id=doc_id,
                )

            if entity_ids:
                session.run(
                    """
                    UNWIND $entity_ids AS entity_id
                    MATCH (e:Entity {id: entity_id})
                    OPTIONAL MATCH (:Document)-[m:MENTIONS]->(e)
                    WITH e, count(m) as mention_count, min(m.first_seen) as first_mentioned,
                         max(m.last_seen) as last_mentioned
                    SET e.mention_count = mention_count,
                        e.first_mentioned = first_mentioned,
                        e.last_mentioned = last_mentioned,
                        e.updated_at = $now
                    """,
                    entity_ids=entity_ids,
                    now=datetime.utcnow().isoformat(),
                )

            if doc_count == 0 and deleted_doc_rels == 0:
                return {
                    "deleted_documents": 0,
                    "deleted_chunks": deleted_chunks,
                    "deleted_document_relationships": 0,
                    "pruned_entities": 0,
                }

            pruned = self.prune_orphan_entities(session=session)
            pruned_chunks = self.prune_orphan_chunks(session=session)
            return {
                "deleted_documents": doc_count,
                "deleted_chunks": deleted_chunks + pruned_chunks,
                "deleted_document_relationships": deleted_doc_rels,
                "pruned_entities": pruned,
            }

    def reconcile_documents(self, valid_document_ids: list[str]) -> dict[str, int]:
        """
        Remove stale graph documents absent from the source document store.

        This is a safety net for historical partial failures where a Document
        node may have been written to Neo4j but the source document no longer
        exists in the vector store.
        """
        valid_ids = [doc_id for doc_id in valid_document_ids if doc_id]

        with self._session() as session:
            stale_record = session.run(
                """
                MATCH (d:Document)
                WHERE NOT d.id IN $valid_ids
                RETURN collect(d.id) as stale_ids
                """,
                valid_ids=valid_ids,
            ).single()

        stale_ids = (
            [doc_id for doc_id in (stale_record["stale_ids"] or []) if doc_id]
            if stale_record
            else []
        )
        if not stale_ids:
            return {
                "stale_documents_found": 0,
                "deleted_documents": 0,
                "deleted_document_relationships": 0,
                "pruned_entities": 0,
            }

        summary = {
            "stale_documents_found": len(stale_ids),
            "deleted_documents": 0,
            "deleted_document_relationships": 0,
            "pruned_entities": 0,
        }
        for stale_id in stale_ids:
            deleted = self.delete_document_graph_data(stale_id)
            summary["deleted_documents"] += int(deleted.get("deleted_documents", 0))
            summary["deleted_document_relationships"] += int(
                deleted.get("deleted_document_relationships", 0)
            )
            summary["pruned_entities"] += int(deleted.get("pruned_entities", 0))

        return summary

    def clear_all_data(self) -> dict[str, int]:
        """Delete all graph nodes and relationships."""
        with self._session() as session:
            rel_record = session.run(
                """
                MATCH ()-[r]->()
                WITH collect(r) as rels, size(collect(r)) as rel_count
                FOREACH (rel IN rels | DELETE rel)
                RETURN rel_count
                """
            ).single()
            rel_count = int(rel_record["rel_count"] or 0) if rel_record else 0

            node_record = session.run(
                """
                MATCH (n)
                WITH collect(n) as nodes, size(collect(n)) as node_count
                FOREACH (node IN nodes | DELETE node)
                RETURN node_count
                """
            ).single()
            node_count = int(node_record["node_count"] or 0) if node_record else 0

            return {"deleted_nodes": node_count, "deleted_relationships": rel_count}

    def prune_orphan_entities(self, session=None) -> int:
        """Delete entity nodes no longer connected to lexical/custom graph."""
        owns_session = session is None
        if owns_session:
            session = self._session()

        try:
            legacy_record = session.run(
                """
                MATCH (e:Entity)
                WHERE NOT (:Document)-[:MENTIONS]->(e)
                  AND NOT (e)--(:Entity)
                WITH collect(e) as entities, size(collect(e)) as pruned
                FOREACH (entity IN entities | DELETE entity)
                RETURN pruned
                """
            ).single()

            graphrag_record = session.run(
                """
                MATCH (e:__Entity__)
                WHERE NOT (e)--()
                WITH collect(e) as entities, size(collect(e)) as pruned
                FOREACH (entity IN entities | DELETE entity)
                RETURN pruned
                """
            ).single()

            legacy_pruned = int(legacy_record["pruned"] or 0) if legacy_record else 0
            graphrag_pruned = int(graphrag_record["pruned"] or 0) if graphrag_record else 0
            return legacy_pruned + graphrag_pruned
        finally:
            if owns_session:
                session.close()

    def prune_orphan_chunks(self, session=None) -> int:
        """Delete chunk nodes that are no longer connected to any document."""
        owns_session = session is None
        if owns_session:
            session = self._session()

        try:
            record = session.run(
                """
                MATCH (c:Chunk)
                WHERE NOT (c)-[:FROM_DOCUMENT]->(:Document)
                WITH collect(c) as chunks, size(collect(c)) as pruned
                FOREACH (chunk IN chunks | DELETE chunk)
                RETURN pruned
                """
            ).single()
            return int(record["pruned"] or 0) if record else 0
        finally:
            if owns_session:
                session.close()

    def clear_graph(self) -> None:
        """Backward-compatible alias for clearing all graph data."""
        self.clear_all_data()

    # =========================================================================
    # Entity Operations
    # =========================================================================

    def create_entity(
        self,
        entity_id: str,
        name: str,
        entity_type: EntityType,
        entity_key: str,
        normalized_name: str,
        aliases: list[str] | None = None,
        alias_norms: list[str] | None = None,
        properties: dict[str, Any] | None = None,
    ) -> str:
        """Create or merge an entity node by canonical key."""
        with self._session() as session:
            now = datetime.utcnow().isoformat()
            label = entity_type.value
            aliases = [alias for alias in (aliases or []) if alias]
            alias_norms = [alias for alias in (alias_norms or []) if alias]
            props = dict(properties or {})
            for reserved in {
                "id",
                "name",
                "key",
                "type",
                "aliases",
                "alias_norms",
                "mention_count",
                "first_mentioned",
                "last_mentioned",
                "created_at",
                "updated_at",
                "normalized_name",
            }:
                props.pop(reserved, None)

            result = session.run(
                f"""
                MERGE (e:Entity:{label} {{key: $key}})
                ON CREATE SET
                    e.id = $entity_id,
                    e.name = $name,
                    e.type = $entity_type,
                    e.normalized_name = $normalized_name,
                    e.aliases = $aliases,
                    e.alias_norms = $alias_norms,
                    e.mention_count = 0,
                    e.created_at = $now,
                    e.updated_at = $now,
                    e.graph_version = $graph_version
                ON MATCH SET
                    e.updated_at = $now,
                    e.type = COALESCE(e.type, $entity_type),
                    e.normalized_name = COALESCE(e.normalized_name, $normalized_name),
                    e.name = CASE
                        WHEN e.name IS NULL OR trim(e.name) = "" THEN $name
                        ELSE e.name
                    END,
                    e.graph_version = $graph_version
                SET e += $props
                SET e.aliases = reduce(
                    acc = [],
                    value IN coalesce(e.aliases, []) + $aliases |
                    CASE WHEN value IN acc THEN acc ELSE acc + value END
                )
                SET e.alias_norms = reduce(
                    acc = [],
                    value IN coalesce(e.alias_norms, []) + $alias_norms |
                    CASE WHEN value IN acc THEN acc ELSE acc + value END
                )
                RETURN e.id as entity_id
                """,
                key=entity_key,
                entity_id=entity_id,
                name=name,
                entity_type=entity_type.value,
                normalized_name=normalized_name,
                aliases=aliases,
                alias_norms=alias_norms,
                now=now,
                graph_version=GRAPH_VERSION,
                props=props,
            )
            record = result.single()
            return str(record["entity_id"]) if record and record["entity_id"] else entity_id

    def get_entity(self, entity_id: str) -> Entity | None:
        """Get an entity by ID."""
        with self._session() as session:
            result = session.run(
                """
                MATCH (e {id: $id})
                WHERE e:Entity OR e:__Entity__
                RETURN e, labels(e) as labels
                """,
                id=entity_id,
            )
            record = result.single()
            if not record:
                return None

            return self._record_to_entity(record)

    def get_all_entities(
        self,
        entity_type: EntityType | None = None,
        limit: int = 100,
    ) -> list[Entity]:
        """Get all entities, optionally filtered by type."""
        with self._session() as session:
            result = session.run(
                """
                MATCH (e)
                WHERE (e:Entity OR e:__Entity__)
                  AND (
                      $entity_type IS NULL
                      OR e.type = $entity_type
                      OR $entity_type IN labels(e)
                  )
                RETURN e, labels(e) as labels
                ORDER BY coalesce(e.mention_count, 0) DESC, e.name
                LIMIT $limit
                """,
                entity_type=entity_type.value if entity_type else None,
                limit=limit,
            )
            return [self._record_to_entity(record) for record in result]

    def update_entity_mention(
        self,
        entity_id: str,
        document_date: datetime | None = None,
    ) -> None:
        """Refresh mention tracking for an entity."""
        with self._session() as session:
            session.run(
                """
                MATCH (e:Entity {id: $id})
                OPTIONAL MATCH (:Document)-[m:MENTIONS]->(e)
                WITH e, count(m) as mention_count, min(m.first_seen) as first_mentioned,
                     max(m.last_seen) as last_mentioned
                SET e.mention_count = mention_count,
                    e.first_mentioned = first_mentioned,
                    e.last_mentioned = last_mentioned,
                    e.updated_at = $now
                """,
                id=entity_id,
                now=datetime.utcnow().isoformat(),
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
        """Create a relationship between two entities with per-document provenance."""
        if rel_type == RelationshipType.MENTIONS:
            self.link_document_to_entity(source_id, target_id, properties=properties)
            return

        props = dict(properties or {})
        doc_id = str(props.pop("document_id", "")).strip()
        if not doc_id:
            # Fallback keeps relationships queryable even if provenance is missing.
            doc_id = "unknown"

        now = datetime.utcnow().isoformat()
        props["graph_version"] = GRAPH_VERSION

        with self._session() as session:
            query = f"""
                MATCH (a:Entity {{id: $source_id}})
                MATCH (b:Entity {{id: $target_id}})
                MERGE (a)-[r:{rel_type.value} {{document_id: $document_id}}]->(b)
                ON CREATE SET r.created_at = $created_at, r.graph_version = $graph_version
                SET r += $props
                SET r.updated_at = $created_at
            """
            session.run(
                query,
                source_id=source_id,
                target_id=target_id,
                document_id=doc_id,
                created_at=now,
                graph_version=GRAPH_VERSION,
                props=props,
            )

    def link_document_to_entity(
        self,
        doc_id: str,
        entity_id: str,
        properties: dict[str, Any] | None = None,
        document_date: datetime | None = None,
    ) -> None:
        """Link a document to an entity via idempotent MENTIONS relationship."""
        rel_props = dict(properties or {})
        rel_props.pop("count", None)
        rel_props.pop("first_seen", None)
        rel_props.pop("last_seen", None)
        rel_props["graph_version"] = GRAPH_VERSION
        date_iso = document_date.isoformat() if document_date else None

        with self._session() as session:
            session.run(
                """
                MATCH (d:Document {id: $doc_id})
                MATCH (e:Entity {id: $entity_id})
                MERGE (d)-[m:MENTIONS]->(e)
                ON CREATE SET
                    m.count = 1,
                    m.first_seen = $date,
                    m.last_seen = $date,
                    m.graph_version = $graph_version
                ON MATCH SET
                    m.first_seen = CASE
                        WHEN $date IS NULL THEN m.first_seen
                        WHEN m.first_seen IS NULL OR m.first_seen > $date THEN $date
                        ELSE m.first_seen
                    END,
                    m.last_seen = CASE
                        WHEN $date IS NULL THEN m.last_seen
                        WHEN m.last_seen IS NULL OR m.last_seen < $date THEN $date
                        ELSE m.last_seen
                    END,
                    m.graph_version = $graph_version
                SET m += $props
                WITH e
                OPTIONAL MATCH (:Document)-[all_mentions:MENTIONS]->(e)
                WITH e,
                     count(all_mentions) as mention_count,
                     min(all_mentions.first_seen) as first_mentioned,
                     max(all_mentions.last_seen) as last_mentioned
                SET e.mention_count = mention_count,
                    e.first_mentioned = first_mentioned,
                    e.last_mentioned = last_mentioned,
                    e.updated_at = $now
                """,
                doc_id=doc_id,
                entity_id=entity_id,
                date=date_iso,
                graph_version=GRAPH_VERSION,
                now=datetime.utcnow().isoformat(),
                props=rel_props,
            )

    def get_entity_relationships(
        self,
        entity_id: str,
    ) -> list[Relationship]:
        """Get all relationships for an entity with relationship metadata."""
        with self._session() as session:
            result = session.run(
                """
                MATCH (e {id: $id})
                WHERE e:Entity OR e:__Entity__
                MATCH (e)-[r]-(other)
                RETURN type(r) as rel_type,
                       startNode(r).id as source_id,
                       endNode(r).id as target_id,
                       properties(r) as props,
                       id(r) as rel_id,
                       other.id as other_id,
                       labels(other) as other_labels,
                       coalesce(other.name, other.filename, other.id) as other_label
                """,
                id=entity_id,
            )

            relationships: list[Relationship] = []
            for record in result:
                rel_type_value = record["rel_type"]
                try:
                    rel_type = RelationshipType(rel_type_value)
                except ValueError:
                    continue

                rel_props = dict(record["props"] or {})
                rel_props["other_id"] = record["other_id"]
                rel_props["other_label"] = record["other_label"]
                rel_props["other_labels"] = record["other_labels"] or []

                doc_id = rel_props.get("document_id")
                relationships.append(
                    Relationship(
                        id=str(record["rel_id"]),
                        source_id=record["source_id"],
                        target_id=record["target_id"],
                        type=rel_type,
                        properties=rel_props,
                        document_ids=[doc_id] if doc_id else [],
                    )
                )

            return relationships

    def get_entity_documents(
        self,
        entity_id: str,
    ) -> list[dict[str, Any]]:
        """Get all documents that mention an entity."""
        with self._session() as session:
            result = session.run(
                """
                MATCH (e {id: $id})
                WHERE e:Entity OR e:__Entity__
                OPTIONAL MATCH (d:Document)-[m:MENTIONS]->(e)
                OPTIONAL MATCH (e)-[:FROM_CHUNK]->(:Chunk)-[:FROM_DOCUMENT]->(d2:Document)
                WITH collect(DISTINCT {doc: d, mention_props: properties(m)}) +
                     collect(DISTINCT {doc: d2, mention_props: {}}) AS rows
                UNWIND rows AS row
                WITH row WHERE row.doc IS NOT NULL
                RETURN row.doc as d, row.mention_props as mention_props
                ORDER BY coalesce(d.date, d.created_at) DESC
                """,
                id=entity_id,
            )

            documents: list[dict[str, Any]] = []
            for record in result:
                doc = dict(record["d"])
                mention_props = dict(record["mention_props"] or {})
                if mention_props:
                    doc["mention"] = mention_props
                documents.append(doc)
            return documents

    # =========================================================================
    # Graph Queries
    # =========================================================================

    def get_graph_data(
        self,
        entity_types: list[EntityType] | None = None,
        max_nodes: int = 100,
    ) -> GraphData:
        """Get graph data for visualization."""
        with self._session() as session:
            result = session.run(
                """
                MATCH (n)
                WHERE (n:Entity OR n:__Entity__)
                  AND (
                      $entity_types IS NULL
                      OR n.type IN $entity_types
                      OR any(label IN labels(n) WHERE label IN $entity_types)
                  )
                RETURN n, labels(n) as labels
                ORDER BY coalesce(n.mention_count, 0) DESC, n.name
                LIMIT $limit
                """,
                entity_types=[et.value for et in entity_types] if entity_types else None,
                limit=max_nodes,
            )

            nodes: list[GraphNode] = []
            node_ids: list[str] = []
            seen_ids: set[str] = set()

            for record in result:
                node = dict(record["n"])
                node_id = node.get("id")
                if not node_id or node_id in seen_ids:
                    continue
                seen_ids.add(node_id)

                etype = self._node_to_entity_type(node, record["labels"])
                nodes.append(
                    GraphNode(
                        id=node_id,
                        label=node.get("name", node_id),
                        type=etype,
                        properties=node,
                    )
                )
                node_ids.append(node_id)

            if not node_ids:
                return GraphData(nodes=[], edges=[])

            edge_result = session.run(
                """
                MATCH (a)-[r]->(b)
                WHERE a.id IN $ids
                  AND b.id IN $ids
                  AND (a:Entity OR a:__Entity__)
                  AND (b:Entity OR b:__Entity__)
                  AND type(r) <> 'MENTIONS'
                RETURN a.id as source,
                       b.id as target,
                       type(r) as rel_type,
                       count(r) as weight,
                       count(DISTINCT r.document_id) as document_count,
                       collect(DISTINCT r.document_id)[0..5] as sample_document_ids,
                       max(coalesce(r.confidence, 0.0)) as max_confidence
                """,
                ids=node_ids,
            )

            edges: list[GraphEdge] = []
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
                        properties={
                            "weight": int(record["weight"] or 0),
                            "document_count": int(record["document_count"] or 0),
                            "sample_document_ids": record["sample_document_ids"] or [],
                            "max_confidence": float(record["max_confidence"] or 0.0),
                            "graph_version": GRAPH_VERSION,
                        },
                    )
                )

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
        with self._session() as session:
            where_clauses = ["d.date IS NOT NULL"]
            params: dict[str, Any] = {}

            if start_date:
                where_clauses.append("d.date >= $start_date")
                params["start_date"] = start_date.isoformat()
            if end_date:
                where_clauses.append("d.date <= $end_date")
                params["end_date"] = end_date.isoformat()

            result = session.run(
                f"""
                MATCH (d:Document)
                WHERE {' AND '.join(where_clauses)}
                RETURN d
                ORDER BY d.date
                """,
                **params,
            )

            by_date: dict[date, list[TimelineDocument]] = defaultdict(list)
            earliest: date | None = None
            latest: date | None = None

            for record in result:
                doc = dict(record["d"])
                try:
                    doc_date = datetime.fromisoformat(doc["date"]).date()
                except (KeyError, TypeError, ValueError):
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
        with self._session() as session:
            result = session.run(
                """
                OPTIONAL MATCH (d:Document)
                WITH count(d) as docs
                OPTIONAL MATCH (p:Person)
                WITH docs, count(p) as persons
                OPTIONAL MATCH (o:Organization)
                WITH docs, persons, count(o) as orgs
                OPTIONAL MATCH (l:Location)
                WITH docs, persons, orgs, count(l) as locations
                OPTIONAL MATCH (e:Event)
                WITH docs, persons, orgs, locations, count(e) as events
                OPTIONAL MATCH (a)-[r]->(b)
                WHERE (a:Entity OR a:__Entity__)
                  AND (b:Entity OR b:__Entity__)
                  AND type(r) <> 'MENTIONS'
                WITH docs, persons, orgs, locations, events, count(r) as rels
                RETURN docs, persons, orgs, locations, events, rels
                """
            )
            record = result.single()
            if not record:
                return {
                    "documents": 0,
                    "persons": 0,
                    "organizations": 0,
                    "locations": 0,
                    "events": 0,
                    "relationships": 0,
                }

            return {
                "documents": int(record["docs"] or 0),
                "persons": int(record["persons"] or 0),
                "organizations": int(record["orgs"] or 0),
                "locations": int(record["locations"] or 0),
                "events": int(record["events"] or 0),
                "relationships": int(record["rels"] or 0),
            }

    # =========================================================================
    # Helpers
    # =========================================================================

    def _record_to_entity(self, record) -> Entity:
        node = dict(record["e"])
        labels = record["labels"]
        entity_type = self._node_to_entity_type(node, labels)

        return Entity(
            id=node["id"],
            name=node.get("name", ""),
            type=entity_type,
            aliases=node.get("aliases", []) or [],
            properties=node,
            mention_count=int(node.get("mention_count") or 0),
            first_mentioned=self._parse_datetime(node.get("first_mentioned")),
            last_mentioned=self._parse_datetime(node.get("last_mentioned")),
        )

    def _node_to_entity_type(self, node: dict[str, Any], labels: list[str]) -> EntityType:
        type_value = node.get("type")
        if type_value:
            try:
                return EntityType(type_value)
            except ValueError:
                pass

        for label in labels:
            try:
                return EntityType(label)
            except ValueError:
                continue

        return EntityType.PERSON

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None


# Module-level instance
_client: Neo4jClient | None = None


def get_neo4j_client() -> Neo4jClient:
    """Get or create the Neo4j client instance."""
    global _client
    if _client is None:
        _client = Neo4jClient()
        _client.initialize_schema()
    return _client
