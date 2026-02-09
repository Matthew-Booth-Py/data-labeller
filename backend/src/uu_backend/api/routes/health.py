"""Health check endpoint."""

from fastapi import APIRouter

from uu_backend import __version__
from uu_backend.config import get_settings
from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.llm.openai_client import get_openai_client

router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Check API health and service status.

    Returns service status and version information.
    """
    # Check vector store connection
    try:
        store = get_vector_store()
        doc_count = store.count()
        vector_db_status = "connected"
    except Exception as e:
        doc_count = 0
        vector_db_status = f"error: {str(e)}"

    # Check Neo4j connection
    try:
        neo4j_client = get_neo4j_client()
        if neo4j_client.verify_connectivity():
            neo4j_status = "connected"
            graph_stats = neo4j_client.get_stats()
        else:
            neo4j_status = "disconnected"
            graph_stats = {}
    except Exception as e:
        neo4j_status = f"error: {str(e)}"
        graph_stats = {}

    # Check OpenAI availability
    try:
        openai_client = get_openai_client()
        openai_status = "available" if openai_client.is_available() else "not configured"
    except Exception:
        openai_status = "not configured"

    # Determine overall health
    all_connected = (
        vector_db_status == "connected"
        and neo4j_status == "connected"
    )

    return {
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
