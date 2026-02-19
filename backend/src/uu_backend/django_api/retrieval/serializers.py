"""Serializers for Contextual Retrieval API."""

from rest_framework import serializers


class SearchQuerySerializer(serializers.Serializer):
    """Request serializer for search endpoint."""

    q = serializers.CharField(
        help_text="Search query",
        required=True,
    )
    top_k = serializers.IntegerField(
        help_text="Number of results to return",
        default=20,
        min_value=1,
        max_value=100,
    )
    document_id = serializers.CharField(
        help_text="Filter results to specific document",
        required=False,
        allow_null=True,
    )
    use_reranking = serializers.BooleanField(
        help_text="Whether to apply reranking",
        default=True,
    )


class SearchResultSerializer(serializers.Serializer):
    """Serializer for a single search result."""

    doc_id = serializers.CharField()
    chunk_index = serializers.IntegerField()
    text = serializers.CharField()
    original_text = serializers.CharField()
    context = serializers.CharField()
    score = serializers.FloatField()


class SearchResponseSerializer(serializers.Serializer):
    """Response serializer for search endpoint."""

    results = SearchResultSerializer(many=True)
    total = serializers.IntegerField()
    query = serializers.CharField()


class IndexDocumentRequestSerializer(serializers.Serializer):
    """Request serializer for index document endpoint."""

    document_id = serializers.CharField(
        help_text="Document ID to index",
        required=True,
    )


class IndexDocumentResponseSerializer(serializers.Serializer):
    """Response serializer for index document endpoint."""

    status = serializers.CharField()
    document_id = serializers.CharField()
    task_id = serializers.CharField(required=False, allow_null=True)


class RetrievalStatsSerializer(serializers.Serializer):
    """Serializer for retrieval index statistics."""

    vector_store_count = serializers.IntegerField()
    bm25_index_count = serializers.IntegerField()
    reranker_type = serializers.CharField()
