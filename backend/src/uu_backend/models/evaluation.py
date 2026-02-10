"""Evaluation models for extraction quality assessment."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FieldEvaluation(BaseModel):
    """Evaluation metrics for a single field."""

    field_name: str = Field(..., description="Field name from schema")
    extracted_value: Any = Field(None, description="Value extracted by system")
    ground_truth_value: Any = Field(None, description="Ground truth value from annotations")
    is_correct: bool = Field(..., description="Whether extraction matches ground truth")
    is_present: bool = Field(..., description="Whether field exists in ground truth")
    is_extracted: bool = Field(..., description="Whether field was extracted")
    confidence: Optional[float] = Field(None, description="Extraction confidence score")
    r2_score: Optional[float] = Field(None, description="R² score for numerical fields (array of numbers)")


class ExtractionEvaluationMetrics(BaseModel):
    """Aggregated metrics for extraction evaluation."""

    # Field-level metrics
    total_fields: int = Field(..., description="Total fields in schema")
    correct_fields: int = Field(..., description="Correctly extracted fields")
    incorrect_fields: int = Field(..., description="Incorrectly extracted fields")
    missing_fields: int = Field(..., description="Fields not extracted (false negatives)")
    extra_fields: int = Field(..., description="Fields extracted but not in ground truth (false positives)")

    # Accuracy metrics
    accuracy: float = Field(..., description="Correct / Total", ge=0.0, le=1.0)
    precision: float = Field(..., description="Correct / (Correct + Incorrect)", ge=0.0, le=1.0)
    recall: float = Field(..., description="Correct / (Correct + Missing)", ge=0.0, le=1.0)
    f1_score: float = Field(..., description="Harmonic mean of precision and recall", ge=0.0, le=1.0)

    # Field-level details
    field_evaluations: list[FieldEvaluation] = Field(
        default_factory=list, description="Per-field evaluation details"
    )


class PromptVersion(BaseModel):
    """A version of an extraction prompt."""

    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Version name (e.g., 'v1.0', 'baseline', 'improved-dates')")
    document_type_id: Optional[str] = Field(None, description="Document type this prompt is for")
    system_prompt: str = Field(..., description="System prompt content")
    user_prompt_template: Optional[str] = Field(None, description="User prompt template with placeholders")
    description: Optional[str] = Field(None, description="Description of changes in this version")
    is_active: bool = Field(False, description="Whether this is the active version")
    created_by: Optional[str] = Field(None, description="User who created this version")
    created_at: datetime = Field(..., description="Creation timestamp")


class PromptVersionCreate(BaseModel):
    """Request model for creating a prompt version."""

    name: str = Field(..., min_length=1, max_length=100)
    document_type_id: Optional[str] = None
    system_prompt: str = Field(..., min_length=1)
    user_prompt_template: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = Field(False, description="Set as active version")
    created_by: Optional[str] = None


class PromptVersionUpdate(BaseModel):
    """Request model for updating a prompt version."""

    name: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ExtractionEvaluation(BaseModel):
    """A single evaluation run comparing extraction vs ground truth."""

    id: str = Field(..., description="Unique identifier")
    document_id: str = Field(..., description="Document evaluated")
    document_type_id: str = Field(..., description="Document type")
    prompt_version_id: Optional[str] = Field(None, description="Prompt version used")
    prompt_version_name: Optional[str] = Field(None, description="Prompt version name (joined)")
    
    # Metrics
    metrics: ExtractionEvaluationMetrics = Field(..., description="Evaluation metrics")
    
    # Metadata
    extraction_time_ms: Optional[int] = Field(None, description="Time taken for extraction")
    evaluated_by: Optional[str] = Field(None, description="User who ran evaluation")
    evaluated_at: datetime = Field(..., description="Evaluation timestamp")
    notes: Optional[str] = Field(None, description="Notes about this evaluation")


class ExtractionEvaluationCreate(BaseModel):
    """Request model for creating an evaluation."""

    document_id: str = Field(..., description="Document to evaluate")
    prompt_version_id: Optional[str] = Field(None, description="Prompt version to use (null = current active)")
    use_llm_refinement: bool = Field(True, description="Whether to use LLM refinement (annotation-based only)")
    use_structured_output: bool = Field(False, description="Use OpenAI structured output (bypasses annotations)")
    evaluated_by: Optional[str] = None
    notes: Optional[str] = None


class ProjectEvaluationCreate(BaseModel):
    """Request model for batch evaluation of a project."""

    document_type_id: str = Field(..., description="Document type (project) to evaluate")
    prompt_version_id: Optional[str] = Field(None, description="Prompt version to use (null = current active)")
    use_llm_refinement: bool = Field(True, description="Whether to use LLM refinement (annotation-based only)")
    use_structured_output: bool = Field(False, description="Use OpenAI structured output (bypasses annotations)")
    evaluated_by: Optional[str] = None
    notes: Optional[str] = None


class ExtractionEvaluationResponse(BaseModel):
    """Response model for a single evaluation."""

    evaluation: ExtractionEvaluation


class ExtractionEvaluationListResponse(BaseModel):
    """Response model for listing evaluations."""

    evaluations: list[ExtractionEvaluation]
    total: int


class ProjectEvaluationResponse(BaseModel):
    """Response model for batch project evaluation."""

    evaluations: list[ExtractionEvaluation]
    total: int
    successful: int
    failed: int


class EvaluationSummary(BaseModel):
    """Aggregated evaluation summary across multiple documents."""

    prompt_version_id: Optional[str] = Field(None, description="Prompt version")
    prompt_version_name: Optional[str] = Field(None, description="Prompt version name")
    document_type_id: Optional[str] = Field(None, description="Document type filter")
    
    # Aggregated metrics
    total_evaluations: int = Field(..., description="Number of evaluations")
    avg_accuracy: float = Field(..., description="Average accuracy")
    avg_precision: float = Field(..., description="Average precision")
    avg_recall: float = Field(..., description="Average recall")
    avg_f1_score: float = Field(..., description="Average F1 score")
    
    # Field-level aggregates
    field_performance: dict[str, dict[str, float]] = Field(
        default_factory=dict,
        description="Per-field metrics: {field_name: {accuracy, precision, recall}}"
    )
    
    # Time range
    earliest_evaluation: Optional[datetime] = None
    latest_evaluation: Optional[datetime] = None


class EvaluationSummaryResponse(BaseModel):
    """Response model for evaluation summary."""

    summary: EvaluationSummary


class PromptComparisonResponse(BaseModel):
    """Response model for comparing multiple prompt versions."""

    comparisons: list[EvaluationSummary]
    document_type_id: Optional[str] = None
