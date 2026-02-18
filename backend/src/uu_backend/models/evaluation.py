"""Evaluation models for comparing ground truth vs predictions."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MatchType(str, Enum):
    """Type of match between ground truth and predicted value."""
    
    EXACT = "exact"  # Direct equality
    NORMALIZED = "normalized"  # After normalization (currency, dates, etc.)
    FUZZY = "fuzzy"  # String similarity match
    SEMANTIC = "semantic"  # LLM-determined semantic equivalence
    NO_MATCH = "no_match"  # Values don't match


class MatchResult(BaseModel):
    """Result of comparing two values."""
    
    is_match: bool = Field(..., description="Whether values match")
    match_type: MatchType = Field(..., description="Type of match")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Match confidence")
    reason: Optional[str] = Field(None, description="Explanation for match/mismatch")


class FieldComparison(BaseModel):
    """Comparison result for a single field."""
    
    field_name: str = Field(..., description="Field name")
    ground_truth_value: Any = Field(..., description="Ground truth value")
    predicted_value: Any = Field(None, description="Predicted value (None if missing)")
    match_result: MatchResult = Field(..., description="Match result")
    instance_num: Optional[int] = Field(None, description="Instance number for array fields")
    
    @property
    def is_correct(self) -> bool:
        """Whether the prediction is correct."""
        return self.match_result.is_match
    
    @property
    def is_missing(self) -> bool:
        """Whether the field is missing from predictions."""
        return self.predicted_value is None
    
    @property
    def is_extra(self) -> bool:
        """Whether the field is extra (predicted but not in ground truth)."""
        return self.ground_truth_value is None and self.predicted_value is not None


class InstanceComparison(BaseModel):
    """Comparison result for an array instance."""
    
    parent_field: str = Field(..., description="Parent array field name")
    instance_num: int = Field(..., description="Instance number")
    gt_instance_num: Optional[int] = Field(None, description="Matched GT instance number")
    pred_instance_num: Optional[int] = Field(None, description="Matched predicted instance number")
    field_comparisons: list[FieldComparison] = Field(default_factory=list)
    is_matched: bool = Field(..., description="Whether instance was matched")
    match_score: float = Field(..., ge=0.0, le=1.0, description="Instance match quality")


class FlattenedMetrics(BaseModel):
    """Metrics treating all fields independently."""
    
    total_fields: int = Field(..., description="Total fields in ground truth")
    correct_fields: int = Field(..., description="Correctly predicted fields")
    incorrect_fields: int = Field(..., description="Incorrectly predicted fields")
    missing_fields: int = Field(..., description="Fields in GT but not predicted")
    extra_fields: int = Field(..., description="Fields predicted but not in GT")
    
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Correct / Total GT fields")
    precision: float = Field(..., ge=0.0, le=1.0, description="Correct / Total predicted")
    recall: float = Field(..., ge=0.0, le=1.0, description="Correct / Total GT")
    f1_score: float = Field(..., ge=0.0, le=1.0, description="Harmonic mean of P and R")
    
    match_type_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Count of each match type"
    )


class InstanceMetrics(BaseModel):
    """Metrics for array instances."""
    
    total_instances: int = Field(..., description="Total instances in ground truth")
    matched_instances: int = Field(..., description="Correctly matched instances")
    missing_instances: int = Field(..., description="GT instances not found in predictions")
    extra_instances: int = Field(..., description="Predicted instances not in GT")
    
    instance_match_rate: float = Field(..., ge=0.0, le=1.0, description="Matched / Total GT")
    avg_field_accuracy_in_matched: float = Field(
        ..., ge=0.0, le=1.0,
        description="Average field accuracy within matched instances"
    )
    
    instance_precision: float = Field(..., ge=0.0, le=1.0)
    instance_recall: float = Field(..., ge=0.0, le=1.0)
    instance_f1_score: float = Field(..., ge=0.0, le=1.0)


class FieldMetrics(BaseModel):
    """Per-field performance metrics."""
    
    field_name: str = Field(..., description="Field name")
    total_occurrences: int = Field(..., description="Times field appears in GT")
    correct_predictions: int = Field(..., description="Correct predictions")
    incorrect_predictions: int = Field(..., description="Incorrect predictions")
    missing_predictions: int = Field(..., description="Missing predictions")
    
    accuracy: float = Field(..., ge=0.0, le=1.0)
    precision: float = Field(..., ge=0.0, le=1.0)
    recall: float = Field(..., ge=0.0, le=1.0)
    
    avg_confidence: float = Field(..., ge=0.0, le=1.0, description="Average match confidence")
    match_type_distribution: dict[str, int] = Field(default_factory=dict)


class EvaluationMetrics(BaseModel):
    """Complete evaluation metrics."""
    
    flattened: FlattenedMetrics = Field(..., description="Flattened view metrics")
    instance_metrics: dict[str, InstanceMetrics] = Field(
        default_factory=dict,
        description="Instance-aware metrics by parent field"
    )
    field_metrics: dict[str, FieldMetrics] = Field(
        default_factory=dict,
        description="Per-field metrics"
    )


class EvaluationResult(BaseModel):
    """Complete evaluation result for a document."""
    
    document_id: str = Field(..., description="Document ID")
    metrics: EvaluationMetrics = Field(..., description="Evaluation metrics")
    field_comparisons: list[FieldComparison] = Field(
        default_factory=list,
        description="Detailed field comparisons"
    )
    instance_comparisons: dict[str, list[InstanceComparison]] = Field(
        default_factory=dict,
        description="Instance comparisons by parent field"
    )
    extraction_time_ms: Optional[float] = Field(None, description="Extraction time")
    evaluation_time_ms: Optional[float] = Field(None, description="Evaluation time")


class EvaluationRun(BaseModel):
    """Stored evaluation run with metadata."""
    
    id: str = Field(..., description="Evaluation run ID")
    document_id: str = Field(..., description="Document ID")
    project_id: Optional[str] = Field(None, description="Project ID")
    result: EvaluationResult = Field(..., description="Evaluation result")
    notes: Optional[str] = Field(None, description="Optional notes")
    evaluated_at: datetime = Field(..., description="Evaluation timestamp")


class EvaluationRunCreate(BaseModel):
    """Request to create an evaluation run."""
    
    document_id: str = Field(..., description="Document ID to evaluate")
    project_id: Optional[str] = Field(None, description="Project ID")
    run_extraction: bool = Field(True, description="Whether to run extraction")
    notes: Optional[str] = Field(None, description="Optional notes")


class EvaluationSummary(BaseModel):
    """Aggregate evaluation metrics across multiple runs."""
    
    project_id: Optional[str] = Field(None, description="Project ID")
    total_evaluations: int = Field(..., description="Number of evaluation runs")
    total_documents: int = Field(..., description="Number of unique documents")
    
    avg_accuracy: float = Field(..., ge=0.0, le=1.0)
    avg_precision: float = Field(..., ge=0.0, le=1.0)
    avg_recall: float = Field(..., ge=0.0, le=1.0)
    avg_f1_score: float = Field(..., ge=0.0, le=1.0)
    
    field_performance: dict[str, FieldMetrics] = Field(
        default_factory=dict,
        description="Aggregated field metrics"
    )
    
    match_type_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Overall match type distribution"
    )


class EvaluationRunListResponse(BaseModel):
    """Response for listing evaluation runs."""
    
    runs: list[EvaluationRun]
    total: int


class EvaluationRunResponse(BaseModel):
    """Response for a single evaluation run."""
    
    run: EvaluationRun
