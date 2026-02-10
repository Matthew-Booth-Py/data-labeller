"""Tests for benchmark dataset and regression-gating evaluation."""

import sys
import types
from datetime import datetime
from pathlib import Path

# Minimal chromadb stub for test environments without optional dependency.
if "chromadb" not in sys.modules:
    chromadb_module = types.ModuleType("chromadb")
    chromadb_config_module = types.ModuleType("chromadb.config")

    class _DummyCollection:
        def get(self, **_kwargs):
            return {"ids": [], "documents": [], "metadatas": []}

        def upsert(self, **_kwargs):
            return None

        def delete(self, **_kwargs):
            return None

    class _DummyPersistentClient:
        def __init__(self, *args, **kwargs):
            pass

        def get_or_create_collection(self, *args, **kwargs):
            return _DummyCollection()

    class _DummySettings:
        def __init__(self, *args, **kwargs):
            pass

    chromadb_module.PersistentClient = _DummyPersistentClient
    chromadb_config_module.Settings = _DummySettings
    sys.modules["chromadb"] = chromadb_module
    sys.modules["chromadb.config"] = chromadb_config_module

from uu_backend.database.sqlite_client import SQLiteClient
from uu_backend.models.evaluation import ExtractionEvaluation, ExtractionEvaluationMetrics, FieldEvaluation
from uu_backend.services.evaluation_service import EvaluationService


def _make_eval(doc_id: str, f1: float, correct: bool) -> ExtractionEvaluation:
    field_eval = FieldEvaluation(
        field_name="invoice_total",
        extracted_value="100",
        ground_truth_value="100",
        is_correct=correct,
        is_present=True,
        is_extracted=True,
    )
    metrics = ExtractionEvaluationMetrics(
        total_fields=1,
        correct_fields=1 if correct else 0,
        incorrect_fields=0 if correct else 1,
        missing_fields=0,
        extra_fields=0,
        accuracy=1.0 if correct else 0.0,
        precision=1.0 if correct else 0.0,
        recall=1.0 if correct else 0.0,
        f1_score=f1,
        field_evaluations=[field_eval],
    )
    return ExtractionEvaluation(
        id=f"eval-{doc_id}",
        document_id=doc_id,
        document_type_id="type-1",
        prompt_version_id=None,
        prompt_version_name=None,
        metrics=metrics,
        extraction_time_ms=10,
        evaluated_by="test",
        evaluated_at=datetime.utcnow(),
        notes=None,
    )


class _FakeSQLite:
    def __init__(self):
        self._run = None

    def get_benchmark_dataset(self, dataset_id: str):
        if dataset_id != "dataset-1":
            return None
        return {
            "id": "dataset-1",
            "name": "Benchmark",
            "document_type_id": "type-1",
            "documents": [
                {"document_id": "doc-a", "split": "test", "doc_subtype": "invoice"},
                {"document_id": "doc-b", "split": "validation", "doc_subtype": "invoice"},
            ],
        }

    def get_benchmark_run(self, run_id: str):
        if run_id == "baseline-1":
            return {"overall_metrics": {"accuracy": 0.25, "precision": 0.25, "recall": 0.25, "f1_score": 0.25}}
        return None

    def save_benchmark_run(self, run: dict):
        self._run = run


def test_evaluate_benchmark_aggregates_and_applies_gates(monkeypatch):
    service = EvaluationService.__new__(EvaluationService)
    fake_sqlite = _FakeSQLite()
    service.sqlite_client = fake_sqlite

    eval_map = {
        "doc-a": _make_eval("doc-a", 1.0, True),
        "doc-b": _make_eval("doc-b", 0.0, False),
    }

    def _fake_eval_extraction(**kwargs):
        return eval_map[kwargs["document_id"]]

    monkeypatch.setattr(service, "evaluate_extraction", _fake_eval_extraction)

    run = service.evaluate_benchmark(
        dataset_id="dataset-1",
        baseline_run_id="baseline-1",
        required_field_gates={"invoice_total": {"min_f1": 0.6, "min_recall": 0.6}},
    )

    assert run.total_documents == 2
    assert run.successful_documents == 2
    assert run.failed_documents == 0
    assert "test" in run.split_metrics
    assert "validation" in run.split_metrics
    assert "invoice" in run.subtype_scorecards
    assert run.drift_delta is not None
    assert run.passed_gates is False
    assert len(run.gate_results) == 1
    assert fake_sqlite._run is not None


def test_sqlite_benchmark_dataset_crud(tmp_path: Path):
    client = SQLiteClient(str(tmp_path / "taxonomy.db"))
    dataset = client.create_benchmark_dataset(
        {
            "name": "Smoke",
            "document_type_id": "dt-1",
            "description": "benchmark",
            "created_by": "tester",
        }
    )
    client.add_benchmark_dataset_document(
        dataset_id=dataset["id"],
        document_id="doc-1",
        split="test",
        tags=["golden"],
        doc_subtype="invoice",
    )

    loaded = client.get_benchmark_dataset(dataset["id"])
    assert loaded is not None
    assert loaded["name"] == "Smoke"
    assert len(loaded["documents"]) == 1
    assert loaded["documents"][0]["split"] == "test"
