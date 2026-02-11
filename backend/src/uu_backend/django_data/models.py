"""Phase 4 ORM models (initial parity skeleton)."""

from django.db import models


class DocumentTypeModel(models.Model):
    """Parity-oriented model for document_types."""

    id = models.CharField(primary_key=True, max_length=64)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    schema_fields = models.JSONField(default=list)
    system_prompt = models.TextField(blank=True, null=True)
    post_processing = models.TextField(blank=True, null=True)
    extraction_model = models.CharField(max_length=128, blank=True, null=True)
    ocr_engine = models.CharField(max_length=128, blank=True, null=True)
    schema_version_id = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "document_types"
