"""Views for Contextual Retrieval API."""

import logging

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.services.contextual_retrieval import get_contextual_retrieval_service

from .serializers import (
    SearchQuerySerializer,
    SearchResponseSerializer,
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
