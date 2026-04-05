from .models import Chunk, ContextualizedChunk, SearchResult


def get_contextual_retrieval_service():
    from .service import get_contextual_retrieval_service as _get_contextual_retrieval_service

    return _get_contextual_retrieval_service()

__all__ = [
    "get_contextual_retrieval_service",
    "Chunk",
    "ContextualizedChunk",
    "SearchResult",
]
