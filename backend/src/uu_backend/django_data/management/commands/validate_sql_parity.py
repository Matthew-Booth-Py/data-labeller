"""Validate SQLite vs Django ORM table row-count parity."""

import sqlite3
from pathlib import Path

from django.core.management.base import BaseCommand

from uu_backend.config import get_settings
from uu_backend.django_data import models as orm


class Command(BaseCommand):
    help = "Compare row counts between legacy SQLite tables and Django ORM tables"

    _MAPPINGS = [
        ("document_types", orm.DocumentTypeModel),
        ("classifications", orm.ClassificationModel),
        ("labels", orm.LabelModel),
        ("annotations", orm.AnnotationModel),
        ("feedback", orm.FeedbackModel),
        ("model_status", orm.ModelStatusModel),
        ("extractions", orm.ExtractionModel),
        ("prompt_versions", orm.PromptVersionModel),
        ("field_prompt_versions", orm.FieldPromptVersionModel),
        ("evaluations", orm.EvaluationModel),
        ("benchmark_datasets", orm.BenchmarkDatasetModel),
        ("benchmark_dataset_documents", orm.BenchmarkDatasetDocumentModel),
        ("benchmark_runs", orm.BenchmarkRunModel),
        ("schema_versions", orm.SchemaVersionModel),
        ("deployment_versions", orm.DeploymentVersionModel),
        ("llm_provider_settings", orm.LLMProviderSettingsModel),
        ("llm_provider_models", orm.LLMProviderModelModel),
        ("global_fields", orm.GlobalFieldModel),
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--sqlite-path",
            default="",
            help="Optional path to legacy SQLite DB (defaults to SQLITE_DATABASE_PATH setting)",
        )

    def handle(self, *args, **options):
        settings = get_settings()
        sqlite_override = options["sqlite_path"].strip()
        sqlite_path = Path(sqlite_override or settings.sqlite_database_path)
        if not sqlite_path.exists():
            self.stdout.write(self.style.ERROR(f"SQLite database not found: {sqlite_path}"))
            return

        mismatches = []
        with sqlite3.connect(str(sqlite_path)) as conn:
            cursor = conn.cursor()
            for table_name, model in self._MAPPINGS:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                sqlite_count = cursor.fetchone()[0]
                orm_count = model.objects.count()
                status = "OK" if sqlite_count == orm_count else "MISMATCH"
                self.stdout.write(f"{table_name:28} sqlite={sqlite_count:6d} orm={orm_count:6d} {status}")
                if sqlite_count != orm_count:
                    mismatches.append((table_name, sqlite_count, orm_count))

        if mismatches:
            self.stdout.write(self.style.ERROR(f"Parity check failed for {len(mismatches)} tables"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS("Parity check passed for all mapped tables"))
