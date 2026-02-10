"""Tests for extraction evaluation system."""

import pytest
from datetime import datetime
from uuid import uuid4

from uu_backend.models.evaluation import (
    ExtractionEvaluationMetrics,
    FieldEvaluation,
    PromptVersion,
)
from uu_backend.services.evaluation_service import EvaluationService


class TestEvaluationService:
    """Test evaluation service."""

    def test_normalize_value_strings(self):
        """Test value normalization for strings."""
        service = EvaluationService()
        
        # Test string normalization
        assert service._normalize_value("  Hello World  ") == "hello world"
        assert service._normalize_value("UPPERCASE") == "uppercase"
        assert service._normalize_value(None) is None

    def test_normalize_value_lists(self):
        """Test value normalization for lists."""
        service = EvaluationService()
        
        # Test list normalization
        assert service._normalize_value(["B", "A", "C"]) == ["a", "b", "c"]
        assert service._normalize_value([1, 2, 3]) == [1.0, 2.0, 3.0]

    def test_normalize_value_numbers(self):
        """Test value normalization for numbers."""
        service = EvaluationService()
        
        # Test number normalization
        assert service._normalize_value(42) == 42.0
        assert service._normalize_value(3.14) == 3.14

    def test_evaluate_field_correct(self):
        """Test field evaluation when extraction is correct."""
        service = EvaluationService()
        
        field_eval = service._evaluate_field(
            field_name="invoice_number",
            extracted_value="INV-12345",
            ground_truth_value="INV-12345"
        )
        
        assert field_eval.field_name == "invoice_number"
        assert field_eval.is_correct is True
        assert field_eval.is_present is True
        assert field_eval.is_extracted is True

    def test_evaluate_field_incorrect(self):
        """Test field evaluation when extraction is incorrect."""
        service = EvaluationService()
        
        field_eval = service._evaluate_field(
            field_name="total_amount",
            extracted_value="1500.00",
            ground_truth_value="2000.00"
        )
        
        assert field_eval.field_name == "total_amount"
        assert field_eval.is_correct is False
        assert field_eval.is_present is True
        assert field_eval.is_extracted is True

    def test_evaluate_field_missing(self):
        """Test field evaluation when field is missing."""
        service = EvaluationService()
        
        field_eval = service._evaluate_field(
            field_name="date",
            extracted_value=None,
            ground_truth_value="2024-01-15"
        )
        
        assert field_eval.field_name == "date"
        assert field_eval.is_correct is False
        assert field_eval.is_present is True
        assert field_eval.is_extracted is False

    def test_evaluate_field_extra(self):
        """Test field evaluation when field is extra (not in ground truth)."""
        service = EvaluationService()
        
        field_eval = service._evaluate_field(
            field_name="extra_field",
            extracted_value="some value",
            ground_truth_value=None
        )
        
        assert field_eval.field_name == "extra_field"
        assert field_eval.is_correct is False
        assert field_eval.is_present is False
        assert field_eval.is_extracted is True

    def test_calculate_metrics_perfect(self):
        """Test metrics calculation with perfect extraction."""
        service = EvaluationService()
        
        field_evaluations = [
            FieldEvaluation(
                field_name="field1",
                extracted_value="value1",
                ground_truth_value="value1",
                is_correct=True,
                is_present=True,
                is_extracted=True,
            ),
            FieldEvaluation(
                field_name="field2",
                extracted_value="value2",
                ground_truth_value="value2",
                is_correct=True,
                is_present=True,
                is_extracted=True,
            ),
        ]
        
        metrics = service._calculate_metrics(field_evaluations)
        
        assert metrics.total_fields == 2
        assert metrics.correct_fields == 2
        assert metrics.incorrect_fields == 0
        assert metrics.missing_fields == 0
        assert metrics.extra_fields == 0
        assert metrics.accuracy == 1.0
        assert metrics.precision == 1.0
        assert metrics.recall == 1.0
        assert metrics.f1_score == 1.0

    def test_calculate_metrics_mixed(self):
        """Test metrics calculation with mixed results."""
        service = EvaluationService()
        
        field_evaluations = [
            # Correct
            FieldEvaluation(
                field_name="field1",
                extracted_value="value1",
                ground_truth_value="value1",
                is_correct=True,
                is_present=True,
                is_extracted=True,
            ),
            # Incorrect
            FieldEvaluation(
                field_name="field2",
                extracted_value="wrong",
                ground_truth_value="value2",
                is_correct=False,
                is_present=True,
                is_extracted=True,
            ),
            # Missing
            FieldEvaluation(
                field_name="field3",
                extracted_value=None,
                ground_truth_value="value3",
                is_correct=False,
                is_present=True,
                is_extracted=False,
            ),
            # Extra
            FieldEvaluation(
                field_name="field4",
                extracted_value="extra",
                ground_truth_value=None,
                is_correct=False,
                is_present=False,
                is_extracted=True,
            ),
        ]
        
        metrics = service._calculate_metrics(field_evaluations)
        
        assert metrics.total_fields == 4
        assert metrics.correct_fields == 1
        assert metrics.incorrect_fields == 1
        assert metrics.missing_fields == 1
        assert metrics.extra_fields == 1
        
        # Accuracy: 1/4 = 0.25
        assert metrics.accuracy == 0.25
        
        # Precision: correct / (correct + incorrect + extra) = 1/3
        assert abs(metrics.precision - 0.333) < 0.01
        
        # Recall: correct / (correct + incorrect + missing) = 1/3
        assert abs(metrics.recall - 0.333) < 0.01
        
        # F1 should be same as precision and recall when they're equal
        assert abs(metrics.f1_score - 0.333) < 0.01

    def test_calculate_metrics_no_extractions(self):
        """Test metrics calculation when nothing is extracted."""
        service = EvaluationService()
        
        field_evaluations = [
            FieldEvaluation(
                field_name="field1",
                extracted_value=None,
                ground_truth_value="value1",
                is_correct=False,
                is_present=True,
                is_extracted=False,
            ),
            FieldEvaluation(
                field_name="field2",
                extracted_value=None,
                ground_truth_value="value2",
                is_correct=False,
                is_present=True,
                is_extracted=False,
            ),
        ]
        
        metrics = service._calculate_metrics(field_evaluations)
        
        assert metrics.total_fields == 2
        assert metrics.correct_fields == 0
        assert metrics.missing_fields == 2
        assert metrics.accuracy == 0.0
        assert metrics.precision == 0.0  # No extractions, so precision is 0
        assert metrics.recall == 0.0
        assert metrics.f1_score == 0.0


class TestPromptVersionModel:
    """Test prompt version model."""

    def test_prompt_version_creation(self):
        """Test creating a prompt version."""
        pv = PromptVersion(
            id=str(uuid4()),
            name="v1.0",
            document_type_id=None,
            system_prompt="Test system prompt",
            user_prompt_template="Test user prompt: {content}",
            description="Initial version",
            is_active=True,
            created_by="test_user",
            created_at=datetime.utcnow(),
        )
        
        assert pv.name == "v1.0"
        assert pv.is_active is True
        assert pv.description == "Initial version"


class TestFieldEvaluationModel:
    """Test field evaluation model."""

    def test_field_evaluation_correct(self):
        """Test field evaluation model for correct extraction."""
        fe = FieldEvaluation(
            field_name="test_field",
            extracted_value="test_value",
            ground_truth_value="test_value",
            is_correct=True,
            is_present=True,
            is_extracted=True,
        )
        
        assert fe.is_correct is True
        assert fe.is_present is True
        assert fe.is_extracted is True


class TestEvaluationMetricsModel:
    """Test evaluation metrics model."""

    def test_metrics_validation(self):
        """Test that metrics are properly validated."""
        metrics = ExtractionEvaluationMetrics(
            total_fields=10,
            correct_fields=8,
            incorrect_fields=1,
            missing_fields=1,
            extra_fields=0,
            accuracy=0.8,
            precision=0.89,
            recall=0.89,
            f1_score=0.89,
            field_evaluations=[],
        )
        
        assert metrics.total_fields == 10
        assert metrics.correct_fields == 8
        assert 0.0 <= metrics.accuracy <= 1.0
        assert 0.0 <= metrics.precision <= 1.0
        assert 0.0 <= metrics.recall <= 1.0
        assert 0.0 <= metrics.f1_score <= 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
