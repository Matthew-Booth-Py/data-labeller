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
    extraction_model = models.CharField(max_length=128, blank=True, null=True)
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


class LabelModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.TextField()
    color = models.TextField(default="#3b82f6")
    description = models.TextField(blank=True, null=True)
    shortcut = models.TextField(blank=True, null=True)
    entity_type = models.TextField(blank=True, null=True)
    document_type_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "labels"
        constraints = [
            models.UniqueConstraint(fields=["name", "document_type_id"], name="idx_labels_name_scope_unique"),
        ]


class AnnotationModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document_id = models.CharField(max_length=64, db_index=True)
    label_id = models.CharField(max_length=64, db_index=True)
    annotation_type = models.TextField()
    start_offset = models.IntegerField(blank=True, null=True)
    end_offset = models.IntegerField(blank=True, null=True)
    text = models.TextField(blank=True, null=True)
    page = models.IntegerField(blank=True, null=True)
    x = models.FloatField(blank=True, null=True)
    y = models.FloatField(blank=True, null=True)
    width = models.FloatField(blank=True, null=True)
    height = models.FloatField(blank=True, null=True)
    key_text = models.TextField(blank=True, null=True)
    key_start = models.IntegerField(blank=True, null=True)
    key_end = models.IntegerField(blank=True, null=True)
    value_text = models.TextField(blank=True, null=True)
    value_start = models.IntegerField(blank=True, null=True)
    value_end = models.IntegerField(blank=True, null=True)
    entity_type = models.TextField(blank=True, null=True)
    normalized_value = models.TextField(blank=True, null=True)
    created_by = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    row_index = models.IntegerField(blank=True, null=True)
    group_id = models.TextField(blank=True, null=True, db_index=True)
    metadata = models.JSONField(default=dict)

    class Meta:
        db_table = "annotations"


class FeedbackModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document_id = models.CharField(max_length=64)
    label_id = models.CharField(max_length=64, db_index=True)
    label_name = models.TextField(blank=True, null=True)
    text = models.TextField()
    start_offset = models.IntegerField()
    end_offset = models.IntegerField()
    feedback_type = models.TextField(db_index=True)
    source = models.TextField()
    embedding = models.JSONField(default=list, blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "feedback"


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


class EvaluationModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document_id = models.CharField(max_length=64, db_index=True)
    document_type_id = models.CharField(max_length=64, db_index=True)
    prompt_version_id = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    schema_version_id = models.CharField(max_length=64, blank=True, null=True)
    comparator_mode = models.TextField(default="normalized")
    metrics = models.JSONField(default=dict)
    extraction_time_ms = models.IntegerField(blank=True, null=True)
    evaluated_by = models.TextField(blank=True, null=True)
    evaluated_at = models.DateTimeField(db_index=True)
    notes = models.TextField(blank=True, null=True)
    field_prompt_versions = models.JSONField(default=dict)

    class Meta:
        db_table = "evaluations"


class BenchmarkDatasetModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    name = models.TextField()
    document_type_id = models.CharField(max_length=64, db_index=True)
    description = models.TextField(blank=True, null=True)
    created_by = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "benchmark_datasets"


class BenchmarkDatasetDocumentModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    dataset_id = models.CharField(max_length=64, db_index=True)
    document_id = models.CharField(max_length=64)
    split = models.TextField(default="test", db_index=True)
    tags = models.JSONField(default=list)
    doc_subtype = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()

    class Meta:
        db_table = "benchmark_dataset_documents"
        constraints = [
            models.UniqueConstraint(fields=["dataset_id", "document_id"], name="unique_dataset_document"),
        ]


class BenchmarkRunModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    dataset_id = models.CharField(max_length=64, db_index=True)
    document_type_id = models.CharField(max_length=64)
    prompt_version_id = models.CharField(max_length=64, blank=True, null=True)
    baseline_run_id = models.CharField(max_length=64, blank=True, null=True)
    total_documents = models.IntegerField()
    successful_documents = models.IntegerField()
    failed_documents = models.IntegerField()
    overall_metrics = models.JSONField(default=dict)
    split_metrics = models.JSONField(default=dict)
    subtype_scorecards = models.JSONField(default=dict)
    confidence_intervals = models.JSONField(default=dict)
    drift_delta = models.JSONField(default=dict, blank=True, null=True)
    gate_results = models.JSONField(default=list, blank=True, null=True)
    passed_gates = models.BooleanField(default=True)
    errors = models.JSONField(default=list, blank=True, null=True)
    use_llm_refinement = models.BooleanField(default=True)
    use_structured_output = models.BooleanField(default=False)
    evaluated_by = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(db_index=True)

    class Meta:
        db_table = "benchmark_runs"


class SchemaVersionModel(models.Model):
    id = models.CharField(primary_key=True, max_length=64)
    document_type_id = models.CharField(max_length=64, db_index=True)
    schema_fields = models.JSONField(default=list)
    system_prompt = models.TextField(blank=True, null=True)
    post_processing = models.TextField(blank=True, null=True)
    extraction_model = models.TextField(blank=True, null=True)
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
    extraction_model = models.TextField(blank=True, null=True)
    ocr_engine = models.TextField(blank=True, null=True)
    created_by = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()

    class Meta:
        db_table = "global_fields"
