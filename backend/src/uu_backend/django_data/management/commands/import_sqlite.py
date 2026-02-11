"""Import legacy SQLite domain data into Django ORM models."""

import json
import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_datetime
from django.utils import timezone

from uu_backend.config import get_settings
from uu_backend.django_data import models as orm


def _parse_json_value(raw, default):
    if raw in (None, ""):
        return default

    def _strip_nul(value):
        if isinstance(value, str):
            return value.replace("\x00", "")
        if isinstance(value, list):
            return [_strip_nul(item) for item in value]
        if isinstance(value, dict):
            return {str(key): _strip_nul(item) for key, item in value.items()}
        return value

    if isinstance(raw, (dict, list)):
        return _strip_nul(raw)
    try:
        parsed = json.loads(str(raw).replace("\x00", ""))
        return _strip_nul(parsed)
    except Exception:
        return default


def _parse_dt(raw):
    if raw in (None, ""):
        return None
    if hasattr(raw, "tzinfo"):
        return timezone.make_aware(raw, timezone.utc) if timezone.is_naive(raw) else raw
    parsed = parse_datetime(str(raw))
    if parsed and timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.utc)
    return parsed


class Command(BaseCommand):
    help = "Import SQLite domain entities into Django ORM for Phase 4 parity migration"

    _TABLES = [
        "document_types",
        "classifications",
        "labels",
        "annotations",
        "feedback",
        "model_status",
        "extractions",
        "prompt_versions",
        "field_prompt_versions",
        "evaluations",
        "benchmark_datasets",
        "benchmark_dataset_documents",
        "benchmark_runs",
        "schema_versions",
        "deployment_versions",
        "llm_provider_settings",
        "llm_provider_models",
        "global_fields",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default="",
            help="Optional path to legacy SQLite DB (defaults to SQLITE_DATABASE_PATH setting)",
        )
        parser.add_argument(
            "--tables",
            default="all",
            help=f"Comma-separated table list or 'all'. Available: {', '.join(self._TABLES)}",
        )

    def handle(self, *args, **options):
        settings = get_settings()
        sqlite_override = options["sqlite_path"].strip()
        sqlite_path = Path(sqlite_override or settings.sqlite_database_path)
        if not sqlite_path.exists():
            self.stdout.write(self.style.ERROR(f"SQLite database not found: {sqlite_path}"))
            return

        requested = options["tables"].strip().lower()
        if requested == "all":
            tables = self._TABLES
        else:
            tables = [part.strip() for part in requested.split(",") if part.strip()]
            invalid = sorted(set(tables) - set(self._TABLES))
            if invalid:
                self.stdout.write(self.style.ERROR(f"Unknown tables: {', '.join(invalid)}"))
                return

        with sqlite3.connect(str(sqlite_path)) as conn:
            conn.row_factory = sqlite3.Row
            for table in tables:
                imported = self._import_table(conn, table)
                self.stdout.write(self.style.SUCCESS(f"{table}: imported {imported} rows"))

    @transaction.atomic
    def _import_table(self, conn: sqlite3.Connection, table: str) -> int:
        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {table}")
        rows = cursor.fetchall()
        imported = 0

        for row in rows:
            data = dict(row)
            model, defaults = self._map_row(table, data)
            if table == "llm_provider_models":
                pk = f"{data['provider']}::{data['model_id']}"
            else:
                pk = data.get("id") or data.get("document_id") or data.get("provider")
            model.objects.update_or_create(pk=pk, defaults=defaults)
            imported += 1
        return imported

    def _map_row(self, table: str, data: dict):
        if table == "document_types":
            return orm.DocumentTypeModel, {
                "name": data["name"],
                "description": data.get("description"),
                "schema_fields": _parse_json_value(data.get("schema_fields"), []),
                "system_prompt": data.get("system_prompt"),
                "post_processing": data.get("post_processing"),
                "extraction_model": data.get("extraction_model"),
                "ocr_engine": data.get("ocr_engine"),
                "schema_version_id": data.get("schema_version_id"),
                "created_at": _parse_dt(data.get("created_at")),
                "updated_at": _parse_dt(data.get("updated_at")),
            }
        if table == "classifications":
            return orm.ClassificationModel, {
                "document_type_id": data["document_type_id"],
                "confidence": data.get("confidence"),
                "labeled_by": data.get("labeled_by"),
                "created_at": _parse_dt(data.get("created_at")),
            }
        if table == "labels":
            return orm.LabelModel, {
                "name": data["name"],
                "color": data.get("color") or "#3b82f6",
                "description": data.get("description"),
                "shortcut": data.get("shortcut"),
                "entity_type": data.get("entity_type"),
                "document_type_id": data.get("document_type_id"),
                "created_at": _parse_dt(data.get("created_at")),
            }
        if table == "annotations":
            return orm.AnnotationModel, {
                "document_id": data["document_id"],
                "label_id": data["label_id"],
                "annotation_type": data["annotation_type"],
                "start_offset": data.get("start_offset"),
                "end_offset": data.get("end_offset"),
                "text": data.get("text"),
                "page": data.get("page"),
                "x": data.get("x"),
                "y": data.get("y"),
                "width": data.get("width"),
                "height": data.get("height"),
                "key_text": data.get("key_text"),
                "key_start": data.get("key_start"),
                "key_end": data.get("key_end"),
                "value_text": data.get("value_text"),
                "value_start": data.get("value_start"),
                "value_end": data.get("value_end"),
                "entity_type": data.get("entity_type"),
                "normalized_value": data.get("normalized_value"),
                "created_by": data.get("created_by"),
                "created_at": _parse_dt(data.get("created_at")),
                "row_index": data.get("row_index"),
                "group_id": data.get("group_id"),
                "metadata": _parse_json_value(data.get("metadata"), {}),
            }
        if table == "feedback":
            return orm.FeedbackModel, {
                "document_id": data["document_id"],
                "label_id": data["label_id"],
                "label_name": data.get("label_name"),
                "text": data["text"],
                "start_offset": data["start_offset"],
                "end_offset": data["end_offset"],
                "feedback_type": data["feedback_type"],
                "source": data["source"],
                "embedding": _parse_json_value(data.get("embedding"), []),
                "created_at": _parse_dt(data.get("created_at")),
            }
        if table == "model_status":
            return orm.ModelStatusModel, {
                "trained_at": _parse_dt(data.get("trained_at")),
                "sample_count": data.get("sample_count") or 0,
                "positive_samples": data.get("positive_samples") or 0,
                "negative_samples": data.get("negative_samples") or 0,
                "labels_count": data.get("labels_count") or 0,
                "accuracy": data.get("accuracy"),
                "model_path": data.get("model_path"),
            }
        if table == "extractions":
            return orm.ExtractionModel, {
                "document_id": data["document_id"],
                "document_type_id": data["document_type_id"],
                "schema_version_id": data.get("schema_version_id"),
                "prompt_version_id": data.get("prompt_version_id"),
                "extracted_data": _parse_json_value(data.get("extracted_data"), {}),
                "extracted_at": _parse_dt(data.get("extracted_at")),
            }
        if table == "prompt_versions":
            return orm.PromptVersionModel, {
                "name": data["name"],
                "document_type_id": data.get("document_type_id"),
                "system_prompt": data["system_prompt"],
                "user_prompt_template": data.get("user_prompt_template"),
                "description": data.get("description"),
                "is_active": bool(data.get("is_active")),
                "created_by": data.get("created_by"),
                "created_at": _parse_dt(data.get("created_at")),
            }
        if table == "field_prompt_versions":
            return orm.FieldPromptVersionModel, {
                "name": data["name"],
                "document_type_id": data["document_type_id"],
                "field_name": data["field_name"],
                "extraction_prompt": data["extraction_prompt"],
                "description": data.get("description"),
                "is_active": bool(data.get("is_active")),
                "created_by": data.get("created_by"),
                "created_at": _parse_dt(data.get("created_at")),
            }
        if table == "evaluations":
            return orm.EvaluationModel, {
                "document_id": data["document_id"],
                "document_type_id": data["document_type_id"],
                "prompt_version_id": data.get("prompt_version_id"),
                "schema_version_id": data.get("schema_version_id"),
                "comparator_mode": data.get("comparator_mode") or "normalized",
                "metrics": _parse_json_value(data.get("metrics"), {}),
                "extraction_time_ms": data.get("extraction_time_ms"),
                "evaluated_by": data.get("evaluated_by"),
                "evaluated_at": _parse_dt(data.get("evaluated_at")),
                "notes": data.get("notes"),
                "field_prompt_versions": _parse_json_value(data.get("field_prompt_versions"), {}),
            }
        if table == "benchmark_datasets":
            return orm.BenchmarkDatasetModel, {
                "name": data["name"],
                "document_type_id": data["document_type_id"],
                "description": data.get("description"),
                "created_by": data.get("created_by"),
                "created_at": _parse_dt(data.get("created_at")),
            }
        if table == "benchmark_dataset_documents":
            return orm.BenchmarkDatasetDocumentModel, {
                "dataset_id": data["dataset_id"],
                "document_id": data["document_id"],
                "split": data.get("split") or "test",
                "tags": _parse_json_value(data.get("tags"), []),
                "doc_subtype": data.get("doc_subtype"),
                "created_at": _parse_dt(data.get("created_at")),
            }
        if table == "benchmark_runs":
            return orm.BenchmarkRunModel, {
                "dataset_id": data["dataset_id"],
                "document_type_id": data["document_type_id"],
                "prompt_version_id": data.get("prompt_version_id"),
                "baseline_run_id": data.get("baseline_run_id"),
                "total_documents": data.get("total_documents") or 0,
                "successful_documents": data.get("successful_documents") or 0,
                "failed_documents": data.get("failed_documents") or 0,
                "overall_metrics": _parse_json_value(data.get("overall_metrics"), {}),
                "split_metrics": _parse_json_value(data.get("split_metrics"), {}),
                "subtype_scorecards": _parse_json_value(data.get("subtype_scorecards"), {}),
                "confidence_intervals": _parse_json_value(data.get("confidence_intervals"), {}),
                "drift_delta": _parse_json_value(data.get("drift_delta"), {}),
                "gate_results": _parse_json_value(data.get("gate_results"), []),
                "passed_gates": bool(data.get("passed_gates")),
                "errors": _parse_json_value(data.get("errors"), []),
                "use_llm_refinement": bool(data.get("use_llm_refinement")),
                "use_structured_output": bool(data.get("use_structured_output")),
                "evaluated_by": data.get("evaluated_by"),
                "notes": data.get("notes"),
                "created_at": _parse_dt(data.get("created_at")),
            }
        if table == "schema_versions":
            return orm.SchemaVersionModel, {
                "document_type_id": data["document_type_id"],
                "schema_fields": _parse_json_value(data.get("schema_fields"), []),
                "system_prompt": data.get("system_prompt"),
                "post_processing": data.get("post_processing"),
                "extraction_model": data.get("extraction_model"),
                "ocr_engine": data.get("ocr_engine"),
                "created_at": _parse_dt(data.get("created_at")),
                "created_by": data.get("created_by"),
            }
        if table == "deployment_versions":
            return orm.DeploymentVersionModel, {
                "project_id": data["project_id"],
                "version": data["version"],
                "document_type_id": data["document_type_id"],
                "document_type_name": data["document_type_name"],
                "schema_version_id": data.get("schema_version_id"),
                "prompt_version_id": data.get("prompt_version_id"),
                "system_prompt": data.get("system_prompt"),
                "user_prompt_template": data.get("user_prompt_template"),
                "schema_fields": _parse_json_value(data.get("schema_fields"), []),
                "field_prompt_versions": _parse_json_value(data.get("field_prompt_versions"), {}),
                "model": data.get("model"),
                "is_active": bool(data.get("is_active")),
                "created_by": data.get("created_by"),
                "created_at": _parse_dt(data.get("created_at")),
            }
        if table == "llm_provider_settings":
            return orm.LLMProviderSettingsModel, {
                "api_key_override": data.get("api_key_override"),
                "last_test_status": data.get("last_test_status") or "unknown",
                "last_tested_at": _parse_dt(data.get("last_tested_at")),
                "updated_at": _parse_dt(data.get("updated_at")),
            }
        if table == "llm_provider_models":
            return orm.LLMProviderModelModel, {
                "provider": data["provider"],
                "model_id": data["model_id"],
                "display_name": data.get("display_name"),
                "is_enabled": bool(data.get("is_enabled")),
                "created_at": _parse_dt(data.get("created_at")),
                "updated_at": _parse_dt(data.get("updated_at")),
            }
        if table == "global_fields":
            return orm.GlobalFieldModel, {
                "name": data["name"],
                "type": data["type"],
                "prompt": data["prompt"],
                "description": data.get("description"),
                "extraction_model": data.get("extraction_model"),
                "ocr_engine": data.get("ocr_engine"),
                "created_by": data.get("created_by"),
                "created_at": _parse_dt(data.get("created_at")),
                "updated_at": _parse_dt(data.get("updated_at")),
            }

        raise ValueError(f"Unsupported table mapping: {table}")
