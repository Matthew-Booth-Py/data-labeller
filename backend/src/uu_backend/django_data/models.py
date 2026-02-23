"""Phase 4 ORM models for SQL parity and Postgres migration."""

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
    
    # Azure DI analysis cache
    azure_di_analysis = models.JSONField(blank=True, null=True)  # Cached Azure DI analysis results
    azure_di_status = models.CharField(max_length=20, default="pending")  # pending, processing, completed, failed
    
    # Contextual retrieval indexing status
    retrieval_index_status = models.CharField(max_length=20, default="pending")  # pending, processing, completed, failed
    retrieval_chunks_count = models.IntegerField(blank=True, null=True)
    retrieval_index_progress = models.IntegerField(blank=True, null=True)  # Current chunk being processed
    retrieval_index_total = models.IntegerField(blank=True, null=True)  # Total chunks to process
    
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
            models.UniqueConstraint(fields=["project_id", "version"], name="idx_deployment_versions_project_version"),
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
