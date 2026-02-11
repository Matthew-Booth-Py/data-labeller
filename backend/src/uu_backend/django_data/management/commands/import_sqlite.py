"""Import SQLite domain data into Django ORM (phase 4 scaffolding)."""

from django.core.management.base import BaseCommand

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.django_data.models import DocumentTypeModel


class Command(BaseCommand):
    help = "Import selected domain entities from legacy SQLite into Django ORM"

    def handle(self, *args, **options):
        sqlite_client = get_sqlite_client()
        count = 0

        for doc_type in sqlite_client.list_document_types():
            DocumentTypeModel.objects.update_or_create(
                id=doc_type.id,
                defaults={
                    "name": doc_type.name,
                    "description": doc_type.description,
                    "schema_fields": [field.model_dump() for field in doc_type.schema_fields],
                    "system_prompt": doc_type.system_prompt,
                    "post_processing": doc_type.post_processing,
                    "extraction_model": doc_type.extraction_model,
                    "ocr_engine": doc_type.ocr_engine,
                    "schema_version_id": doc_type.schema_version_id,
                    "created_at": doc_type.created_at,
                    "updated_at": doc_type.updated_at,
                },
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"Imported {count} document types"))
