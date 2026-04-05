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
    context = serializers.CharField()  # type: ignore[assignment]
    score = serializers.FloatField()
    chunk_id = serializers.CharField(required=False, allow_null=True)
    page_number = serializers.IntegerField(required=False, allow_null=True)
    asset_type = serializers.CharField(required=False, allow_null=True)
    asset_label = serializers.CharField(required=False, allow_null=True)
    citation_id = serializers.CharField(required=False, allow_null=True)
    citation_regions = serializers.JSONField(required=False)
    preview_artifact_id = serializers.CharField(required=False, allow_null=True)


class SearchResponseSerializer(serializers.Serializer):
    """Response serializer for search endpoint."""

    results = SearchResultSerializer(many=True)  # type: ignore[assignment,misc]
    total = serializers.IntegerField()
    query = serializers.CharField()
