"""Phase 4 ORM models for SQL parity and Postgres migration."""
# mypy: disable-error-code="var-annotated"

from django.db import models


class DocumentModel(models.Model):
    """Document storage model - replaces vector store."""

    id = models.CharField(primary_key=True, max_length=64)
    filename = models.CharField(max_length=255, db_index=True)
    file_type = models.CharField(max_length=50)
    content = models.TextField()
    date_extracted = models.DateField(blank=True, null=True, db_index=True)
    created_at = models.DateTimeField(db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    file_path = models.CharField(max_length=512, blank=True, null=True)

    # Contextual retrieval indexing status
    retrieval_index_status = models.CharField(
        max_length=20, default="pending"
    )  # pending, processing, completed, failed
    retrieval_chunks_count = models.IntegerField(blank=True, null=True)
    retrieval_index_progress = models.IntegerField(
        blank=True, null=True
    )  # Current chunk being processed
    retrieval_index_total = models.IntegerField(blank=True, null=True)  # Total chunks to process
    retrieval_index_backend = models.CharField(max_length=64, blank=True, null=True)

    # Metadata fields
    page_count = models.IntegerField(blank=True, null=True)
    word_count = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = "documents"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["filename"]),
            models.Index(fields=["file_type"]),
            models.Index(fields=["date_extracted"]),
        ]


class DocumentTypeModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True, null=True)
    schema_fields = models.JSONField(default=list)
    system_prompt = models.TextField(blank=True, null=True)
    post_processing = models.TextField(blank=True, null=True)
    ocr_engine = models.CharField(max_length=128, blank=True, null=True)
    schema_version_id = models.CharField(max_length=64, blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "document_types"


class ClassificationModel(models.Model):
    document_id = models.CharField(primary_key=True, max_length=64)
    document_type_id = models.CharField(max_length=64, db_index=True)
    confidence = models.FloatField(blank=True, null=True)
    labeled_by = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "classifications"


class ModelStatusModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    trained_at = models.DateTimeField()
    sample_count = models.IntegerField()
    positive_samples = models.IntegerField(default=0)
    negative_samples = models.IntegerField(default=0)
    labels_count = models.IntegerField(default=0)
    accuracy = models.FloatField(blank=True, null=True)
    model_path = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "model_status"


class ExtractionModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document_id = models.CharField(max_length=64, unique=True, db_index=True)
    document_type_id = models.CharField(max_length=64)
    schema_version_id = models.CharField(max_length=64, blank=True, null=True)
    prompt_version_id = models.CharField(max_length=64, blank=True, null=True)
    extracted_data = models.JSONField(default=dict)
    request_metadata = models.JSONField(default=dict)
    request_logs = models.JSONField(default=list)
    extracted_at = models.DateTimeField()

    class Meta:
        db_table = "extractions"


class PromptVersionModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.TextField()
    document_type_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    system_prompt = models.TextField()
    user_prompt_template = models.TextField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=False, db_index=True)
    created_by = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "prompt_versions"


class FieldPromptVersionModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.TextField()
    document_type_id = models.CharField(max_length=64, db_index=True)
    field_name = models.TextField(db_index=True)
    extraction_prompt = models.TextField()
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=False, db_index=True)
    created_by = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "field_prompt_versions"


class SchemaVersionModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document_type_id = models.CharField(max_length=64, db_index=True)
    schema_fields = models.JSONField(default=list)
    system_prompt = models.TextField(blank=True, null=True)
    post_processing = models.TextField(blank=True, null=True)
    ocr_engine = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    created_by = models.TextField(blank=True, null=True)

    class Meta:
        db_table = "schema_versions"


class ProjectModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.CharField(max_length=255, unique=True, db_index=True)
    description = models.TextField(blank=True, null=True)
    type = models.CharField(max_length=100, blank=True, null=True)
    model = models.CharField(max_length=255, blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "projects"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"], name="idx_projects_name"),
            models.Index(fields=["created_at"], name="idx_projects_created"),
        ]


class ProjectDocumentModel(models.Model):
    id = models.BigAutoField(primary_key=True)
    project = models.ForeignKey(
        ProjectModel,
        db_column="project_id",
        on_delete=models.CASCADE,
        related_name="project_documents",
    )
    document = models.ForeignKey(
        DocumentModel,
        db_column="document_id",
        on_delete=models.CASCADE,
        related_name="document_projects",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_documents"
        constraints = [
            models.UniqueConstraint(
                fields=["project", "document"],
                name="uq_project_documents_project_document",
            ),
        ]
        indexes = [
            models.Index(fields=["project", "created_at"], name="idx_project_docs_project"),
            models.Index(fields=["document"], name="idx_project_docs_document"),
        ]


class DeploymentVersionModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    project_id = models.TextField()
    version = models.TextField()
    document_type_id = models.CharField(max_length=64)
    document_type_name = models.TextField()
    schema_version_id = models.CharField(max_length=64, blank=True, null=True)
    prompt_version_id = models.CharField(max_length=64, blank=True, null=True)
    system_prompt = models.TextField(blank=True, null=True)
    user_prompt_template = models.TextField(blank=True, null=True)
    schema_fields = models.JSONField(default=list)
    field_prompt_versions = models.JSONField(default=dict)
    model = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=False)
    created_by = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "deployment_versions"
        constraints = [
            models.UniqueConstraint(
                fields=["project_id", "version"], name="idx_deployment_versions_project_version"
            ),
        ]
        indexes = [
            models.Index(fields=["project_id", "is_active"], name="idx_deploy_project_active"),
            models.Index(fields=["project_id", "created_at"], name="idx_deploy_project_created"),
        ]


class LLMProviderSettingsModel(models.Model):
    provider = models.TextField(primary_key=True)
    api_key_override = models.TextField(blank=True, null=True)
    endpoint_override = models.TextField(blank=True, null=True)
    last_test_status = models.TextField(default="unknown")
    last_tested_at = models.DateTimeField(blank=True, null=True)
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "llm_provider_settings"


class LLMProviderModelModel(models.Model):
    id = models.CharField(primary_key=True, max_length=256)
    provider = models.TextField()
    model_id = models.TextField()
    display_name = models.TextField(blank=True, null=True)
    is_enabled = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "llm_provider_models"
        constraints = [
            models.UniqueConstraint(fields=["provider", "model_id"], name="llm_provider_model_pk"),
        ]
        indexes = [
            models.Index(fields=["provider", "is_enabled"], name="idx_llm_provider_enabled"),
        ]


class GlobalFieldModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.TextField(unique=True, db_index=True)
    type = models.TextField()
    prompt = models.TextField()
    description = models.TextField(blank=True, null=True)
    ocr_engine = models.TextField(blank=True, null=True)
    created_by = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "global_fields"


class GroundTruthAnnotationModel(models.Model):
    """Ground truth annotations for data labelling."""

    id = models.CharField(primary_key=True, max_length=64)
    document_id = models.CharField(max_length=64, db_index=True)
    field_name = models.CharField(max_length=255, db_index=True)
    value = models.JSONField()  # Store any type of value
    annotation_type = models.CharField(max_length=20)  # text_span, bbox, table_row
    annotation_data = models.JSONField()  # Stores coordinates/spans
    confidence = models.FloatField(default=1.0)
    labeled_by = models.CharField(max_length=50)  # manual, ai-suggested, ai-approved
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "ground_truth_annotations"
        indexes = [
            models.Index(fields=["document_id", "field_name"]),
            models.Index(fields=["document_id", "created_at"]),
            models.Index(fields=["labeled_by"]),
        ]


class EvaluationRunModel(models.Model):
    """Evaluation run storage - compares ground truth vs predictions."""

    id = models.CharField(primary_key=True, max_length=64)
    document_id = models.CharField(max_length=64, db_index=True)
    project_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)

    # Evaluation results (stored as JSON for flexibility)
    metrics = models.JSONField()  # EvaluationMetrics
    field_comparisons = models.JSONField()  # List of FieldComparison
    instance_comparisons = models.JSONField(default=dict)  # Dict of InstanceComparison lists

    # Performance metrics
    extraction_time_ms = models.FloatField(blank=True, null=True)
    evaluation_time_ms = models.FloatField(blank=True, null=True)

    # Metadata
    notes = models.TextField(blank=True, null=True)
    evaluated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "evaluation_runs"
        ordering = ["-evaluated_at"]
        indexes = [
            models.Index(fields=["document_id", "-evaluated_at"]),
            models.Index(fields=["project_id", "-evaluated_at"]),
            models.Index(fields=["-evaluated_at"]),
        ]


class RetrievalArtifactModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document = models.ForeignKey(
        DocumentModel,
        db_column="document_id",
        on_delete=models.CASCADE,
        related_name="retrieval_artifacts",
    )
    media_type = models.CharField(max_length=128)
    relative_path = models.CharField(max_length=512, unique=True)
    byte_size = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "retrieval_artifacts"
        indexes = [
            models.Index(fields=["document", "created_at"], name="idx_retrieval_artifact_doc"),
        ]


class RetrievalPageModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document = models.ForeignKey(
        DocumentModel,
        db_column="document_id",
        on_delete=models.CASCADE,
        related_name="retrieval_pages",
    )
    page_number = models.IntegerField()
    width = models.FloatField()
    height = models.FloatField()
    source_width = models.FloatField(default=0.0)
    source_height = models.FloatField(default=0.0)
    rotation = models.IntegerField(default=0)
    text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "retrieval_pages"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "page_number"],
                name="uq_retrieval_pages_document_page",
            ),
        ]
        indexes = [
            models.Index(fields=["document", "page_number"], name="idx_retrieval_page_doc_num"),
        ]


class RetrievalAssetModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document = models.ForeignKey(
        DocumentModel,
        db_column="document_id",
        on_delete=models.CASCADE,
        related_name="retrieval_assets",
    )
    page = models.ForeignKey(
        RetrievalPageModel,
        db_column="page_id",
        on_delete=models.CASCADE,
        related_name="assets",
    )
    asset_type = models.CharField(max_length=32)
    label = models.TextField()
    bbox = models.JSONField(default=list)
    text_content = models.TextField(blank=True, default="")
    preview_artifact = models.ForeignKey(
        RetrievalArtifactModel,
        db_column="preview_artifact_id",
        on_delete=models.SET_NULL,
        related_name="preview_assets",
        blank=True,
        null=True,
    )
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "retrieval_assets"
        indexes = [
            models.Index(fields=["document", "asset_type"], name="idx_retrieval_asset_doc_type"),
            models.Index(fields=["page", "asset_type"], name="idx_retrieval_asset_page_type"),
        ]


class RetrievalChunkModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document = models.ForeignKey(
        DocumentModel,
        db_column="document_id",
        on_delete=models.CASCADE,
        related_name="retrieval_chunks",
    )
    page = models.ForeignKey(
        RetrievalPageModel,
        db_column="page_id",
        on_delete=models.CASCADE,
        related_name="chunks",
    )
    asset = models.ForeignKey(
        RetrievalAssetModel,
        db_column="asset_id",
        on_delete=models.SET_NULL,
        related_name="chunks",
        blank=True,
        null=True,
    )
    chunk_index = models.IntegerField()
    chunk_type = models.CharField(max_length=32)
    content = models.TextField()
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "retrieval_chunks"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "chunk_index"],
                name="uq_retrieval_chunks_document_index",
            ),
        ]
        indexes = [
            models.Index(fields=["document", "chunk_index"], name="idx_retrieval_chunk_doc_idx"),
            models.Index(fields=["page"], name="idx_retrieval_chunk_page"),
        ]


class RetrievalCitationModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document = models.ForeignKey(
        DocumentModel,
        db_column="document_id",
        on_delete=models.CASCADE,
        related_name="retrieval_citations",
    )
    page = models.ForeignKey(
        RetrievalPageModel,
        db_column="page_id",
        on_delete=models.CASCADE,
        related_name="citations",
    )
    chunk = models.OneToOneField(
        RetrievalChunkModel,
        db_column="chunk_id",
        on_delete=models.CASCADE,
        related_name="citation",
    )
    asset = models.ForeignKey(
        RetrievalAssetModel,
        db_column="asset_id",
        on_delete=models.SET_NULL,
        related_name="citations",
        blank=True,
        null=True,
    )
    preview_artifact = models.ForeignKey(
        RetrievalArtifactModel,
        db_column="preview_artifact_id",
        on_delete=models.SET_NULL,
        related_name="preview_citations",
        blank=True,
        null=True,
    )
    label = models.TextField(blank=True, default="")
    bbox = models.JSONField(default=list)
    regions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "retrieval_citations"
        indexes = [
            models.Index(fields=["document", "page"], name="idx_ret_cite_doc_page"),
        ]
