"""DRF views for health endpoints."""

from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend import __version__
from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.llm.openai_client import get_openai_client


class HealthView(APIView):
    """Health status endpoint preserving API response contract."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        try:
            store = get_vector_store()
            doc_count = store.count()
            vector_db_status = "connected"
        except Exception as exc:
            doc_count = 0
            vector_db_status = f"error: {exc}"

        try:
            neo4j_client = get_neo4j_client()
            if neo4j_client.verify_connectivity():
                neo4j_status = "connected"
                graph_stats = neo4j_client.get_stats()
            else:
                neo4j_status = "disconnected"
                graph_stats = {}
        except Exception as exc:
            neo4j_status = f"error: {exc}"
            graph_stats = {}

        try:
            openai_client = get_openai_client()
            openai_status = "available" if openai_client.is_available() else "not configured"
        except Exception:
            openai_status = "not configured"

        all_connected = vector_db_status == "connected" and neo4j_status == "connected"

        return Response(
            {
                "status": "healthy" if all_connected else "degraded",
                "version": __version__,
                "services": {
                    "vector_db": vector_db_status,
                    "neo4j": neo4j_status,
                    "openai": openai_status,
                },
                "stats": {
                    "documents": doc_count,
                    "graph": graph_stats,
                },
            }
        )
