"""
Contextual Retrieval Service

Implements Anthropic's Contextual Retrieval approach:
- Contextual embeddings with chunk-specific context
- Hybrid search (vector + BM25)
- Reranking with Azure Cohere
"""

from .models import Chunk, ContextualizedChunk, SearchResult
from .service import ContextualRetrievalService, get_contextual_retrieval_service

__all__ = [
    "ContextualRetrievalService",
    "get_contextual_retrieval_service",
    "Chunk",
    "ContextualizedChunk",
    "SearchResult",
]
