"""Views for Contextual Retrieval API."""

import logging

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.services.contextual_retrieval import get_contextual_retrieval_service
from uu_backend.tasks.contextual_retrieval_tasks import (
    delete_document_from_retrieval_index,
    index_document_for_retrieval,
)

from .serializers import (
    IndexDocumentResponseSerializer,
    RetrievalStatsSerializer,
    SearchQuerySerializer,
    SearchResponseSerializer,
    SearchResultSerializer,
)

logger = logging.getLogger(__name__)


class SearchView(APIView):
    """Search for relevant document chunks using contextual retrieval."""

    @extend_schema(
        operation_id="search",
        summary="Search documents",
        description=(
            "Search for relevant document chunks using hybrid search "
            "(vector + BM25) with optional reranking."
        ),
        parameters=[
            OpenApiParameter(
                name="q",
                type=str,
                description="Search query",
                required=True,
            ),
            OpenApiParameter(
                name="top_k",
                type=int,
                description="Number of results (default: 20)",
                required=False,
            ),
            OpenApiParameter(
                name="document_id",
                type=str,
                description="Filter to specific document",
                required=False,
            ),
            OpenApiParameter(
                name="use_reranking",
                type=bool,
                description="Apply reranking (default: true)",
                required=False,
            ),
        ],
        responses={200: SearchResponseSerializer},
        tags=["Retrieval"],
    )
    def get(self, request):
        """Search for relevant chunks."""
        serializer = SearchQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        
        query = serializer.validated_data["q"]
        top_k = serializer.validated_data.get("top_k", 20)
        document_id = serializer.validated_data.get("document_id")
        use_reranking = serializer.validated_data.get("use_reranking", True)
        
        service = get_contextual_retrieval_service()
        
        results = service.search(
            query=query,
            top_k=top_k,
            filter_doc_id=document_id,
            use_reranking=use_reranking,
        )
        
        result_data = [
            {
                "doc_id": r.doc_id,
                "chunk_index": r.chunk_index,
                "text": r.text,
                "original_text": r.original_text,
                "context": r.context,
                "score": r.score,
            }
            for r in results
        ]
        
        return Response({
            "results": result_data,
            "total": len(result_data),
            "query": query,
        })


class IndexDocumentView(APIView):
    """Index a document for contextual retrieval."""

    @extend_schema(
        operation_id="index_document",
        summary="Index document for retrieval",
        description=(
            "Trigger async indexing of a document for contextual retrieval. "
            "This will chunk the document, generate context, create embeddings, "
            "and store in the vector and BM25 indexes."
        ),
        responses={202: IndexDocumentResponseSerializer},
        tags=["Retrieval"],
    )
    def post(self, request, document_id):
        """Start async indexing of a document."""
        task = index_document_for_retrieval.delay(document_id)
        
        return Response(
            {
                "status": "indexing_started",
                "document_id": document_id,
                "task_id": task.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )

    @extend_schema(
        operation_id="delete_document_index",
        summary="Delete document from retrieval index",
        description="Remove a document from the contextual retrieval index.",
        responses={202: IndexDocumentResponseSerializer},
        tags=["Retrieval"],
    )
    def delete(self, request, document_id):
        """Delete a document from the index."""
        task = delete_document_from_retrieval_index.delay(document_id)
        
        return Response(
            {
                "status": "deletion_started",
                "document_id": document_id,
                "task_id": task.id,
            },
            status=status.HTTP_202_ACCEPTED,
        )


class RetrievalStatsView(APIView):
    """Get statistics about the retrieval index."""

    @extend_schema(
        operation_id="retrieval_stats",
        summary="Get retrieval index stats",
        description="Get statistics about the contextual retrieval index.",
        responses={200: RetrievalStatsSerializer},
        tags=["Retrieval"],
    )
    def get(self, request):
        """Get index statistics."""
        service = get_contextual_retrieval_service()
        stats = service.get_stats()
        
        return Response(stats)


class DocumentChunksView(APIView):
    """Get indexed chunks for a document."""

    @extend_schema(
        operation_id="get_document_chunks",
        summary="Get document chunks",
        description="Get all indexed chunks for a specific document.",
        responses={200: SearchResultSerializer(many=True)},
        tags=["Retrieval"],
    )
    def get(self, request, document_id):
        """Get chunks for a document."""
        service = get_contextual_retrieval_service()
        chunks = service.get_document_chunks(document_id)
        
        chunk_data = [
            {
                "doc_id": c.doc_id,
                "chunk_index": c.index,
                "text": c.contextualized_text,
                "original_text": c.original_text,
                "context": c.context,
                "score": 0.0,
            }
            for c in chunks
        ]
        
        return Response({
            "document_id": document_id,
            "chunks": chunk_data,
            "total": len(chunk_data),
        })
