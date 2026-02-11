"""DRF views for search and Q&A endpoints."""

from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.services.qa_service import get_qa_service


class SearchView(APIView):
    """Semantic search endpoint preserving API contract."""

    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        query = (request.query_params.get("q") or "").strip()
        if not query:
            return Response({"detail": "Query parameter 'q' is required"}, status=422)

        n_results_raw = request.query_params.get("n_results", "5")
        try:
            n_results = int(n_results_raw)
        except ValueError:
            return Response({"detail": "n_results must be an integer"}, status=422)
        if n_results < 1 or n_results > 50:
            return Response({"detail": "n_results must be between 1 and 50"}, status=422)

        document_ids = request.query_params.get("document_ids")
        doc_ids = [value.strip() for value in document_ids.split(",") if value.strip()] if document_ids else None

        results = get_qa_service().semantic_search(query, n_results, doc_ids)
        payload = {
            "query": query,
            "results": [
                {
                    "document_id": row.get("document_id"),
                    "filename": row.get("filename"),
                    "chunk_index": row.get("chunk_index"),
                    "content": row.get("content"),
                    "similarity": row.get("similarity"),
                }
                for row in results
            ],
            "total": len(results),
        }
        return Response(payload)


class AskView(APIView):
    """RAG question-answer endpoint preserving API contract."""

    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        body = request.data if isinstance(request.data, dict) else {}
        question = (body.get("question") or "").strip()
        if not question:
            return Response({"detail": "question is required"}, status=422)

        document_ids = body.get("document_ids")
        if document_ids is not None and not isinstance(document_ids, list):
            return Response({"detail": "document_ids must be a list when provided"}, status=422)

        n_context = body.get("n_context", 5)
        try:
            n_context = int(n_context)
        except (TypeError, ValueError):
            return Response({"detail": "n_context must be an integer"}, status=422)
        if n_context < 1 or n_context > 20:
            return Response({"detail": "n_context must be between 1 and 20"}, status=422)

        result = get_qa_service().ask(
            question=question,
            document_ids=document_ids,
            n_context=n_context,
        )
        return Response(
            {
                "question": question,
                "answer": result.get("answer", ""),
                "confidence": result.get("confidence", 0.0),
                "sources": result.get("sources", []),
                "referenced_sources": result.get("referenced_sources", []),
            }
        )
