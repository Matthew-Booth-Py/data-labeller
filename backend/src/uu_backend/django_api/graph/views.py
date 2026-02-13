"""DRF views for graph endpoints."""

from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.entity import EntityDetailResponse, EntityListResponse, EntityType
from uu_backend.tasks.neo4j_tasks import index_document_in_neo4j_task


def _compute_indexing_status() -> tuple[int, int, list[str]]:
    """Return (total_docs, indexed_docs, pending_ids)."""
    vector_store = get_vector_store()
    neo4j_client = get_neo4j_client()

    vector_docs = vector_store.get_all_documents()
    vector_doc_ids = {doc.id for doc in vector_docs}
    # Use fully indexed check (based on indexed=True property) instead of just having chunks
    fully_indexed_ids = neo4j_client.get_fully_indexed_document_ids()

    indexed_ids = vector_doc_ids.intersection(fully_indexed_ids)
    pending_ids = sorted(vector_doc_ids - fully_indexed_ids)
    return len(vector_doc_ids), len(indexed_ids), pending_ids


def _resolve_document_ids(document_or_chunk_id: str) -> list[str]:
    """Resolve document IDs from document id, filename, or chunk identifier."""
    raw = (document_or_chunk_id or "").strip()
    if not raw:
        raise ValueError("identifier is empty")

    vector_store = get_vector_store()
    documents = vector_store.get_all_documents()
    document_ids = {doc.id for doc in documents}

    doc_from_chunk = vector_store.get_document_id_for_chunk(raw)
    if doc_from_chunk:
        return [doc_from_chunk]

    if raw in document_ids:
        return [raw]

    exact_name_matches = [doc.id for doc in documents if doc.filename == raw]
    if exact_name_matches:
        return sorted(set(exact_name_matches))

    ci_name_matches = [doc.id for doc in documents if doc.filename.lower() == raw.lower()]
    if ci_name_matches:
        return sorted(set(ci_name_matches))

    for separator in (":", "#", "|"):
        if separator in raw:
            prefix = raw.split(separator, 1)[0].strip()
            if prefix and prefix in document_ids:
                return [prefix]

    raise ValueError("no matching document for provided identifier")


class GraphView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        entity_type_values = request.query_params.getlist("entity_types")
        entity_types = None
        if entity_type_values:
            try:
                entity_types = [EntityType(value) for value in entity_type_values]
            except ValueError as exc:
                return Response({"detail": f"Invalid entity type: {exc}"}, status=422)

        max_nodes_raw = request.query_params.get("max_nodes", "100")
        try:
            max_nodes = int(max_nodes_raw)
        except ValueError:
            return Response({"detail": "max_nodes must be an integer"}, status=422)
        if max_nodes < 1 or max_nodes > 500:
            return Response({"detail": "max_nodes must be between 1 and 500"}, status=422)

        client = get_neo4j_client()
        try:
            graph_data = client.get_graph_data(entity_types=entity_types, max_nodes=max_nodes)
            return Response(graph_data.model_dump(mode="json"))
        except Exception as exc:
            return Response({"detail": f"Failed to retrieve graph data: {exc}"}, status=500)


class GraphEntitiesView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        entity_type_raw = request.query_params.get("entity_type")
        entity_type = None
        if entity_type_raw:
            try:
                entity_type = EntityType(entity_type_raw)
            except ValueError as exc:
                return Response({"detail": f"Invalid entity_type: {exc}"}, status=422)

        limit_raw = request.query_params.get("limit", "100")
        try:
            limit = int(limit_raw)
        except ValueError:
            return Response({"detail": "limit must be an integer"}, status=422)
        if limit < 1 or limit > 500:
            return Response({"detail": "limit must be between 1 and 500"}, status=422)

        client = get_neo4j_client()
        try:
            entities = client.get_all_entities(entity_type=entity_type, limit=limit)
            payload = EntityListResponse(entities=entities, total=len(entities))
            return Response(payload.model_dump(mode="json"))
        except Exception as exc:
            return Response({"detail": f"Failed to retrieve entities: {exc}"}, status=500)


class GraphEntityDetailView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, entity_id: str):
        client = get_neo4j_client()
        try:
            entity = client.get_entity(entity_id)
            if not entity:
                return Response({"detail": f"Entity not found: {entity_id}"}, status=404)

            related_documents = client.get_entity_documents(entity_id)
            relationships = client.get_entity_relationships(entity_id)
            payload = EntityDetailResponse(
                entity=entity,
                related_documents=related_documents,
                relationships=relationships,
            )
            return Response(payload.model_dump(mode="json"))
        except Exception as exc:
            return Response({"detail": f"Failed to retrieve entity: {exc}"}, status=500)


class GraphTimelineView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        start_date_raw = request.query_params.get("start_date")
        end_date_raw = request.query_params.get("end_date")

        try:
            start_date = date.fromisoformat(start_date_raw) if start_date_raw else None
        except ValueError:
            return Response(
                {"detail": "Invalid start_date. Use ISO date format YYYY-MM-DD."},
                status=422,
            )

        try:
            end_date = date.fromisoformat(end_date_raw) if end_date_raw else None
        except ValueError:
            return Response(
                {"detail": "Invalid end_date. Use ISO date format YYYY-MM-DD."},
                status=422,
            )

        client = get_neo4j_client()
        try:
            timeline = client.get_timeline(start_date=start_date, end_date=end_date)
            return Response(timeline.model_dump(mode="json"))
        except Exception as exc:
            return Response({"detail": f"Failed to retrieve timeline: {exc}"}, status=500)


class GraphStatsView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        client = get_neo4j_client()
        try:
            return Response(client.get_stats())
        except Exception as exc:
            return Response({"detail": f"Failed to retrieve graph stats: {exc}"}, status=500)


class GraphIndexingStatusView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        try:
            total_docs, indexed_docs, pending_ids = _compute_indexing_status()
            neo4j_stats = get_neo4j_client().get_stats()
            total_entities = (
                neo4j_stats.get("persons", 0)
                + neo4j_stats.get("organizations", 0)
                + neo4j_stats.get("locations", 0)
                + neo4j_stats.get("events", 0)
            )
            return Response(
                {
                    "total_documents": total_docs,
                    "indexed_documents": indexed_docs,
                    "pending_documents": len(pending_ids),
                    "pending_document_ids": pending_ids,
                    "graph_documents_total": neo4j_stats.get("documents", 0),
                    "graph_entities_total": total_entities,
                    "graph_relationships_total": neo4j_stats.get("relationships", 0),
                }
            )
        except Exception as exc:
            return Response(
                {"detail": f"Failed to retrieve graph indexing status: {exc}"},
                status=500,
            )


class GraphIndexMissingView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        try:
            total_docs, indexed_docs, pending_ids = _compute_indexing_status()
            task_ids: list[str] = []
            for doc_id in pending_ids:
                async_result = index_document_in_neo4j_task.delay(doc_id)
                task_ids.append(async_result.id)

            return Response(
                {
                    "total_documents": total_docs,
                    "indexed_documents": indexed_docs,
                    "pending_documents_before": len(pending_ids),
                    "enqueued_documents": len(task_ids),
                    "enqueued_task_ids": task_ids,
                }
            )
        except Exception as exc:
            return Response(
                {"detail": f"Failed to enqueue graph indexing jobs: {exc}"},
                status=500,
            )


class GraphIndexDocumentsView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        requested = request.data.get("document_ids", [])
        if not isinstance(requested, list):
            return Response({"detail": "document_ids must be a list"}, status=422)

        requested_ids = sorted({str(doc_id).strip() for doc_id in requested if str(doc_id).strip()})
        if not requested_ids:
            return Response({"detail": "document_ids is required"}, status=400)

        try:
            vector_store = get_vector_store()
            neo4j_client = get_neo4j_client()
            vector_doc_ids = {doc.id for doc in vector_store.get_all_documents()}
            # Use fully indexed check (based on indexed=True property) instead of just having chunks
            fully_indexed_ids = neo4j_client.get_fully_indexed_document_ids()

            missing_ids = [doc_id for doc_id in requested_ids if doc_id not in vector_doc_ids]
            eligible_ids = [doc_id for doc_id in requested_ids if doc_id in vector_doc_ids]
            already_indexed_ids = [
                doc_id for doc_id in eligible_ids if doc_id in fully_indexed_ids
            ]
            enqueue_ids = [
                doc_id for doc_id in eligible_ids if doc_id not in fully_indexed_ids
            ]

            task_ids: list[str] = []
            for doc_id in enqueue_ids:
                async_result = index_document_in_neo4j_task.delay(doc_id)
                task_ids.append(async_result.id)

            return Response(
                {
                    "requested_documents": len(requested_ids),
                    "valid_documents": len(eligible_ids),
                    "missing_documents": len(missing_ids),
                    "already_indexed_documents": len(already_indexed_ids),
                    "enqueued_documents": len(enqueue_ids),
                    "enqueued_task_ids": task_ids,
                    "missing_document_ids": missing_ids,
                    "already_indexed_document_ids": already_indexed_ids,
                }
            )
        except Exception as exc:
            return Response(
                {"detail": f"Failed to enqueue specific graph indexing jobs: {exc}"},
                status=500,
            )


class GraphDeleteDbView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def delete(self, request):
        try:
            neo4j_client = get_neo4j_client()
            stats_before = neo4j_client.get_stats()
            neo4j_client.clear_graph()
            stats_after = neo4j_client.get_stats()
            total_docs, indexed_docs, pending_ids = _compute_indexing_status()

            return Response(
                {
                    "deleted": True,
                    "stats_before": stats_before,
                    "stats_after": stats_after,
                    "total_documents": total_docs,
                    "indexed_documents": indexed_docs,
                    "pending_documents": len(pending_ids),
                }
            )
        except Exception as exc:
            return Response({"detail": f"Failed to delete graph database: {exc}"}, status=500)


class GraphRemoveDocumentView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def delete(self, request):
        requested_id = (request.query_params.get("document_or_chunk_id") or "").strip()
        if not requested_id:
            return Response({"detail": "document_or_chunk_id is required"}, status=422)

        try:
            resolved_document_ids = _resolve_document_ids(requested_id)
            neo4j_client = get_neo4j_client()

            removed_document_ids: list[str] = []
            for doc_id in resolved_document_ids:
                if neo4j_client.delete_document(doc_id):
                    removed_document_ids.append(doc_id)

            total_docs, indexed_docs, pending_ids = _compute_indexing_status()
            return Response(
                {
                    "requested_id": requested_id,
                    "resolved_document_id": resolved_document_ids[0],
                    "resolved_document_ids": resolved_document_ids,
                    "removed": len(removed_document_ids) > 0,
                    "removed_documents": len(removed_document_ids),
                    "removed_document_ids": removed_document_ids,
                    "total_documents": total_docs,
                    "indexed_documents": indexed_docs,
                    "pending_documents": len(pending_ids),
                }
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except Exception as exc:
            return Response({"detail": f"Failed to remove graph document: {exc}"}, status=500)
