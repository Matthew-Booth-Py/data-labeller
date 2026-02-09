"""FastAPI application for Unstructured Unlocked."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from uu_backend import __version__
from uu_backend.config import get_settings
from uu_backend.database.neo4j_client import get_neo4j_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.api.routes import health, ingest, timeline, documents, graph, taxonomy, annotations, suggestions, search, tutorial


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup: Initialize connections
    settings = get_settings()

    # Initialize vector store (creates directories if needed)
    vector_store = get_vector_store()
    print(f"Vector store initialized at: {settings.chroma_path}")
    print(f"Documents in vector store: {vector_store.count()}")

    # Initialize Neo4j connection
    try:
        neo4j_client = get_neo4j_client()
        if neo4j_client.verify_connectivity():
            print(f"Neo4j connected at: {settings.neo4j_uri}")
            stats = neo4j_client.get_stats()
            print(f"Neo4j stats: {stats}")
        else:
            print("Warning: Neo4j connection failed")
    except Exception as e:
        print(f"Warning: Neo4j initialization failed: {e}")

    yield

    # Shutdown: Cleanup if needed
    print("Shutting down...")
    try:
        neo4j_client = get_neo4j_client()
        neo4j_client.close()
    except Exception:
        pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Unstructured Unlocked",
        description="Document intelligence API for temporal analysis and Q&A",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(health.router)
    app.include_router(
        ingest.router,
        prefix=settings.api_prefix,
        tags=["ingestion"],
    )
    app.include_router(
        timeline.router,
        prefix=settings.api_prefix,
        tags=["timeline"],
    )
    app.include_router(
        documents.router,
        prefix=settings.api_prefix,
        tags=["documents"],
    )
    app.include_router(
        graph.router,
        prefix=settings.api_prefix,
        tags=["graph"],
    )
    app.include_router(
        taxonomy.router,
        prefix=settings.api_prefix,
        tags=["taxonomy"],
    )
    app.include_router(
        annotations.router,
        prefix=settings.api_prefix,
        tags=["annotations"],
    )
    app.include_router(
        suggestions.router,
        prefix=settings.api_prefix,
        tags=["suggestions"],
    )
    app.include_router(
        search.router,
        prefix=settings.api_prefix,
        tags=["search"],
    )
    app.include_router(
        tutorial.router,
        prefix=settings.api_prefix,
        tags=["tutorial"],
    )

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "uu_backend.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
