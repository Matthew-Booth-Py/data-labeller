"""DRF views for graph endpoints."""

from datetime import date

from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.models.entity import EntityDetailResponse, EntityListResponse, EntityType


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
            return Response({"detail": "Invalid start_date. Use ISO date format YYYY-MM-DD."}, status=422)

        try:
            end_date = date.fromisoformat(end_date_raw) if end_date_raw else None
        except ValueError:
            return Response({"detail": "Invalid end_date. Use ISO date format YYYY-MM-DD."}, status=422)

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
