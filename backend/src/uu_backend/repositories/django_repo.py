"""Django ORM-backed repository adapter."""

import os
from datetime import datetime
from typing import Any
from uuid import uuid4

import django
from django.apps import apps
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uu_backend.django_project.settings.local")
if not apps.ready:
    django.setup()

from uu_backend.config import get_settings
from uu_backend.django_data import models as orm
from uu_backend.models.prompt import FieldPromptVersion, PromptVersion
from uu_backend.models.project import Project, ProjectCreate, ProjectUpdate
from uu_backend.models.taxonomy import (
    Classification,
    DocumentType,
    DocumentTypeCreate,
    DocumentTypeUpdate,
    FieldType,
    GlobalField,
    GlobalFieldCreate,
    GlobalFieldUpdate,
    SchemaField,
)


class DjangoORMRepository:
    @staticmethod
    def _parse_incremental_version(name: str | None) -> int | None:
        if not name:
            return None
        parts = name.strip().split(".")
        if len(parts) != 2 or parts[0] != "0" or not parts[1].isdigit():
            return None
        return int(parts[1])

    @staticmethod
    def _format_incremental_version(minor: int) -> str:
        return f"0.{minor}"

    @staticmethod
    def _iso(value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    @staticmethod
    def _schema_fields_to_payload(schema_fields: list[SchemaField]) -> list[dict[str, Any]]:
        return [field.model_dump(mode="json") for field in schema_fields]

    @staticmethod
    def _schema_fields_from_payload(payload: Any) -> list[SchemaField]:
        if not payload:
            return []
        if not isinstance(payload, list):
            return []
        return [SchemaField.model_validate(item) for item in payload]

    def _document_type_from_model(self, model: orm.DocumentTypeModel) -> DocumentType:
        return DocumentType(
            id=model.id,
            name=model.name,
            description=model.description,
            schema_fields=self._schema_fields_from_payload(model.schema_fields),
            system_prompt=model.system_prompt,
            post_processing=model.post_processing,
            ocr_engine=model.ocr_engine,
            schema_version_id=model.schema_version_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _deployment_from_model(self, model: orm.DeploymentVersionModel) -> dict[str, Any]:
        return {
            "id": model.id,
            "project_id": model.project_id,
            "version": model.version,
            "document_type_id": model.document_type_id,
            "document_type_name": model.document_type_name,
            "schema_version_id": model.schema_version_id,
            "prompt_version_id": model.prompt_version_id,
            "system_prompt": model.system_prompt,
            "user_prompt_template": model.user_prompt_template,
            "schema_fields": model.schema_fields or [],
            "field_prompt_versions": model.field_prompt_versions or {},
            "model": model.model,
            "is_active": bool(model.is_active),
            "created_by": model.created_by,
            "created_at": model.created_at,
        }

    def _global_field_from_model(self, model: orm.GlobalFieldModel) -> GlobalField:
        return GlobalField(
            id=model.id,
            name=model.name,
            type=FieldType(model.type),
            prompt=model.prompt,
            description=model.description,
            ocr_engine=model.ocr_engine,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _project_from_model(self, model: orm.ProjectModel) -> Project:
        document_ids = list(
            model.project_documents.order_by("created_at", "id").values_list("document_id", flat=True)
        )
        return Project(
            id=model.id,
            name=model.name,
            description=model.description or "",
            type=model.type or "Document Analysis",
            model=model.model,
            created_at=model.created_at,
            updated_at=model.updated_at,
            document_ids=document_ids,
            doc_count=len(document_ids),
        )

    def _prompt_version_from_model(self, model: orm.PromptVersionModel) -> PromptVersion:
        return PromptVersion(
            id=model.id,
            name=model.name,
            document_type_id=model.document_type_id,
            system_prompt=model.system_prompt,
            user_prompt_template=model.user_prompt_template,
            description=model.description,
            is_active=bool(model.is_active),
            created_by=model.created_by,
            created_at=model.created_at,
        )

    def _field_prompt_version_from_model(
        self, model: orm.FieldPromptVersionModel
    ) -> FieldPromptVersion:
        return FieldPromptVersion(
            id=model.id,
            name=model.name,
            document_type_id=model.document_type_id,
            field_name=model.field_name,
            extraction_prompt=model.extraction_prompt,
            description=model.description,
            is_active=bool(model.is_active),
            created_by=model.created_by,
            created_at=model.created_at,
        )

    def _next_field_prompt_version_name(self, document_type_id: str, field_name: str) -> str:
        query = orm.FieldPromptVersionModel.objects.filter(
            document_type_id=document_type_id,
            field_name=field_name,
        )
        minors = [
            parsed
            for parsed in (
                self._parse_incremental_version(name)
                for name in query.values_list("name", flat=True)
            )
            if parsed is not None
        ]
        next_minor = (max(minors) + 1) if minors else 0
        return self._format_incremental_version(next_minor)

    def _next_deployment_version_name(self, project_id: str) -> str:
        query = orm.DeploymentVersionModel.objects.filter(project_id=project_id)
        minors = [
            parsed
            for parsed in (
                self._parse_incremental_version(name)
                for name in query.values_list("version", flat=True)
            )
            if parsed is not None
        ]
        next_minor = (max(minors) + 1) if minors else 0
        return self._format_incremental_version(next_minor)

    def health(self) -> dict:
        return {
            "backend": "django",
            "status": "connected",
            "database": connection.vendor,
        }

    @transaction.atomic
    def create_project(self, data: ProjectCreate) -> Project:
        now = timezone.now()
        row = orm.ProjectModel.objects.create(
            id=data.id,
            name=data.name,
            description=data.description,
            type=data.type,
            model=data.model,
            created_at=now,
            updated_at=now,
        )
        return self._project_from_model(row)

    def get_project(self, project_id: str) -> Project | None:
        row = orm.ProjectModel.objects.filter(id=project_id).first()
        return self._project_from_model(row) if row else None

    def list_projects(self) -> list[Project]:
        rows = orm.ProjectModel.objects.order_by("name")
        return [self._project_from_model(row) for row in rows]

    @transaction.atomic
    def update_project(self, project_id: str, data: ProjectUpdate) -> Project | None:
        row = orm.ProjectModel.objects.filter(id=project_id).first()
        if not row:
            return None

        changed_fields: list[str] = []
        if data.name is not None:
            row.name = data.name
            changed_fields.append("name")
        if data.description is not None:
            row.description = data.description
            changed_fields.append("description")
        if data.type is not None:
            row.type = data.type
            changed_fields.append("type")
        if data.model is not None:
            row.model = data.model
            changed_fields.append("model")

        if changed_fields:
            row.updated_at = timezone.now()
            changed_fields.append("updated_at")
            row.save(update_fields=changed_fields)

        return self._project_from_model(row)

    @transaction.atomic
    def delete_project(self, project_id: str) -> bool:
        deleted, _ = orm.ProjectModel.objects.filter(id=project_id).delete()
        return deleted > 0

    @transaction.atomic
    def add_documents_to_project(self, project_id: str, document_ids: list[str]) -> Project | None:
        row = orm.ProjectModel.objects.filter(id=project_id).first()
        if not row:
            return None

        valid_document_ids = set(
            orm.DocumentModel.objects.filter(id__in=document_ids).values_list("id", flat=True)
        )
        for document_id in document_ids:
            if document_id not in valid_document_ids:
                continue
            orm.ProjectDocumentModel.objects.get_or_create(
                project=row,
                document_id=document_id,
            )

        row.updated_at = timezone.now()
        row.save(update_fields=["updated_at"])
        return self._project_from_model(row)

    @transaction.atomic
    def remove_document_from_project(self, project_id: str, document_id: str) -> Project | None:
        row = orm.ProjectModel.objects.filter(id=project_id).first()
        if not row:
            return None

        orm.ProjectDocumentModel.objects.filter(project=row, document_id=document_id).delete()
        row.updated_at = timezone.now()
        row.save(update_fields=["updated_at"])
        return self._project_from_model(row)

    @transaction.atomic
    def create_document_type(self, data: DocumentTypeCreate) -> DocumentType:
        now = timezone.now()
        schema_version_id = str(uuid4())

        row = orm.DocumentTypeModel.objects.create(
            id=str(uuid4()),
            name=data.name,
            description=data.description,
            schema_fields=self._schema_fields_to_payload(data.schema_fields),
            system_prompt=data.system_prompt,
            post_processing=data.post_processing,
            ocr_engine=data.ocr_engine or "native-text",
            schema_version_id=schema_version_id,
            created_at=now,
            updated_at=now,
        )

        orm.SchemaVersionModel.objects.create(
            id=schema_version_id,
            document_type_id=row.id,
            schema_fields=self._schema_fields_to_payload(data.schema_fields),
            system_prompt=data.system_prompt,
            post_processing=data.post_processing,
            ocr_engine=data.ocr_engine or "native-text",
            created_at=now,
            created_by=None,
        )

        return self._document_type_from_model(row)

    def get_document_type(self, type_id: str) -> DocumentType | None:
        row = orm.DocumentTypeModel.objects.filter(id=type_id).first()
        return self._document_type_from_model(row) if row else None

    def get_document_type_by_name(self, name: str) -> DocumentType | None:
        row = orm.DocumentTypeModel.objects.filter(name=name).first()
        return self._document_type_from_model(row) if row else None

    def list_document_types(self) -> list[DocumentType]:
        rows = orm.DocumentTypeModel.objects.order_by("name")
        types = [self._document_type_from_model(row) for row in rows]
        return types

    @transaction.atomic
    def update_document_type(self, type_id: str, data: DocumentTypeUpdate) -> DocumentType | None:
        existing = orm.DocumentTypeModel.objects.filter(id=type_id).first()
        if not existing:
            return None

        updates: dict[str, Any] = {}
        if data.name is not None:
            updates["name"] = data.name
        if data.description is not None:
            updates["description"] = data.description
        if data.schema_fields is not None:
            updates["schema_fields"] = self._schema_fields_to_payload(data.schema_fields)
        if data.system_prompt is not None:
            updates["system_prompt"] = data.system_prompt
        if data.post_processing is not None:
            updates["post_processing"] = data.post_processing
        if data.ocr_engine is not None:
            updates["ocr_engine"] = data.ocr_engine

        requires_new_schema_version = any(
            key in updates
            for key in ("schema_fields", "system_prompt", "post_processing", "ocr_engine")
        )

        if not updates:
            return self._document_type_from_model(existing)

        now = timezone.now()
        updates["updated_at"] = now

        if requires_new_schema_version:
            schema_version_id = str(uuid4())
            updates["schema_version_id"] = schema_version_id

            next_schema_fields = updates.get("schema_fields", existing.schema_fields or [])
            next_system_prompt = updates.get("system_prompt", existing.system_prompt)
            next_post_processing = updates.get("post_processing", existing.post_processing)
            next_ocr_engine = updates.get("ocr_engine", existing.ocr_engine)

            orm.SchemaVersionModel.objects.create(
                id=schema_version_id,
                document_type_id=type_id,
                schema_fields=next_schema_fields,
                system_prompt=next_system_prompt,
                post_processing=next_post_processing,
                ocr_engine=next_ocr_engine,
                created_at=now,
                created_by=None,
            )

        for key, value in updates.items():
            setattr(existing, key, value)
        existing.save(update_fields=list(updates.keys()))

        return self._document_type_from_model(existing)

    @transaction.atomic
    def delete_document_type(self, type_id: str) -> bool:
        orm.ClassificationModel.objects.filter(document_type_id=type_id).delete()
        deleted, _ = orm.DocumentTypeModel.objects.filter(id=type_id).delete()
        return deleted > 0

    def list_schema_versions(self, document_type_id: str) -> list[dict[str, Any]]:
        rows = orm.SchemaVersionModel.objects.filter(document_type_id=document_type_id).order_by(
            "-created_at"
        )
        return [
            {
                "id": row.id,
                "document_type_id": row.document_type_id,
                "schema_fields": row.schema_fields or [],
                "system_prompt": row.system_prompt,
                "post_processing": row.post_processing,
                "ocr_engine": row.ocr_engine,
                "created_at": self._iso(row.created_at),
                "created_by": row.created_by,
            }
            for row in rows
        ]

    @transaction.atomic
    def create_deployment_version(
        self,
        *,
        project_id: str,
        document_type_id: str,
        prompt_version_id: str | None = None,
        created_by: str | None = None,
        set_active: bool = True,
    ) -> dict[str, Any]:
        doc_type = self.get_document_type(document_type_id)
        if not doc_type:
            raise ValueError(f"Document type {document_type_id} not found")

        prompt_version = self.get_prompt_version(prompt_version_id) if prompt_version_id else None
        active_field_prompts = self.list_active_field_prompt_versions(document_type_id)
        active_field_prompt_versions = self.list_active_field_prompt_version_names(document_type_id)

        snapshot_schema_fields: list[dict[str, Any]] = []
        for field in doc_type.schema_fields:
            field_payload = field.model_dump(mode="json")
            prompt_override = active_field_prompts.get(field.name)
            if prompt_override:
                field_payload["extraction_prompt"] = prompt_override
            snapshot_schema_fields.append(field_payload)

        now = timezone.now()
        deployment_id = str(uuid4())
        version = self._next_deployment_version_name(project_id)

        if set_active:
            orm.DeploymentVersionModel.objects.filter(project_id=project_id).update(is_active=False)

        settings = get_settings()
        created = orm.DeploymentVersionModel.objects.create(
            id=deployment_id,
            project_id=project_id,
            version=version,
            document_type_id=document_type_id,
            document_type_name=doc_type.name,
            schema_version_id=doc_type.schema_version_id,
            prompt_version_id=prompt_version_id,
            system_prompt=(
                prompt_version.system_prompt if prompt_version else doc_type.system_prompt
            ),
            user_prompt_template=(prompt_version.user_prompt_template if prompt_version else None),
            schema_fields=snapshot_schema_fields,
            field_prompt_versions=active_field_prompt_versions,
            model=doc_type.extraction_model or settings.effective_tagging_model,
            is_active=set_active,
            created_by=created_by,
            created_at=now,
        )

        return self._deployment_from_model(created)

    def get_deployment_version(self, deployment_version_id: str) -> dict[str, Any] | None:
        row = orm.DeploymentVersionModel.objects.filter(id=deployment_version_id).first()
        return self._deployment_from_model(row) if row else None

    def get_deployment_version_by_name(
        self, project_id: str, version: str
    ) -> dict[str, Any] | None:
        row = orm.DeploymentVersionModel.objects.filter(
            project_id=project_id, version=version
        ).first()
        return self._deployment_from_model(row) if row else None

    def list_deployment_versions(self, project_id: str) -> list[dict[str, Any]]:
        rows = orm.DeploymentVersionModel.objects.filter(project_id=project_id).order_by(
            "-created_at", "-id"
        )
        return [self._deployment_from_model(row) for row in rows]

    def get_active_deployment_version(self, project_id: str) -> dict[str, Any] | None:
        row = (
            orm.DeploymentVersionModel.objects.filter(project_id=project_id, is_active=True)
            .order_by("-created_at", "-id")
            .first()
        )
        return self._deployment_from_model(row) if row else None

    @transaction.atomic
    def activate_deployment_version(
        self, project_id: str, deployment_version_id: str
    ) -> dict[str, Any] | None:
        row = orm.DeploymentVersionModel.objects.filter(
            id=deployment_version_id, project_id=project_id
        ).first()
        if not row:
            return None

        orm.DeploymentVersionModel.objects.filter(project_id=project_id).update(is_active=False)
        row.is_active = True
        row.save(update_fields=["is_active"])
        return self._deployment_from_model(row)

    def create_global_field(self, data: GlobalFieldCreate) -> GlobalField:
        now = timezone.now()
        row = orm.GlobalFieldModel.objects.create(
            id=str(uuid4()),
            name=data.name,
            type=data.type.value,
            prompt=data.prompt,
            description=data.description,
            ocr_engine=data.ocr_engine or "native-text",
            created_by=data.created_by,
            created_at=now,
            updated_at=now,
        )
        return self._global_field_from_model(row)

    def list_global_fields(self, search: str | None = None) -> list[GlobalField]:
        query = orm.GlobalFieldModel.objects.all()
        if search:
            query = query.filter(
                Q(name__icontains=search)
                | Q(prompt__icontains=search)
                | Q(description__icontains=search)
            )
        rows = query.order_by("name")
        return [self._global_field_from_model(row) for row in rows]

    def get_global_field(self, field_id: str) -> GlobalField | None:
        row = orm.GlobalFieldModel.objects.filter(id=field_id).first()
        return self._global_field_from_model(row) if row else None

    def get_global_field_by_name(self, name: str) -> GlobalField | None:
        row = orm.GlobalFieldModel.objects.filter(name=name).first()
        return self._global_field_from_model(row) if row else None

    def update_global_field(self, field_id: str, data: GlobalFieldUpdate) -> GlobalField | None:
        row = orm.GlobalFieldModel.objects.filter(id=field_id).first()
        if not row:
            return None

        changed_fields: list[str] = []
        if data.name is not None:
            row.name = data.name
            changed_fields.append("name")
        if data.type is not None:
            row.type = data.type.value
            changed_fields.append("type")
        if data.prompt is not None:
            row.prompt = data.prompt
            changed_fields.append("prompt")
        if data.description is not None:
            row.description = data.description
            changed_fields.append("description")
        if data.ocr_engine is not None:
            row.ocr_engine = data.ocr_engine
            changed_fields.append("ocr_engine")

        if not changed_fields:
            return self._global_field_from_model(row)

        row.updated_at = timezone.now()
        changed_fields.append("updated_at")
        row.save(update_fields=changed_fields)
        return self._global_field_from_model(row)

    def delete_global_field(self, field_id: str) -> bool:
        deleted, _ = orm.GlobalFieldModel.objects.filter(id=field_id).delete()
        return deleted > 0

    def classify_document(
        self,
        document_id: str,
        document_type_id: str,
        confidence: float | None = None,
        labeled_by: str | None = None,
    ) -> Classification:
        doc_type = self.get_document_type(document_type_id)
        if not doc_type:
            raise ValueError(f"Document type {document_type_id} not found")

        now = timezone.now()
        orm.ClassificationModel.objects.update_or_create(
            document_id=document_id,
            defaults={
                "document_type_id": document_type_id,
                "confidence": confidence,
                "labeled_by": labeled_by,
                "created_at": now,
            },
        )

        return Classification(
            document_id=document_id,
            document_type_id=document_type_id,
            document_type_name=doc_type.name,
            confidence=confidence,
            labeled_by=labeled_by,
            created_at=now,
        )

    def get_classification(self, document_id: str) -> Classification | None:
        row = orm.ClassificationModel.objects.filter(document_id=document_id).first()
        if not row:
            return None

        doc_type_name = (
            orm.DocumentTypeModel.objects.filter(id=row.document_type_id)
            .values_list("name", flat=True)
            .first()
        )
        return Classification(
            document_id=row.document_id,
            document_type_id=row.document_type_id,
            document_type_name=doc_type_name,
            confidence=row.confidence,
            labeled_by=row.labeled_by,
            created_at=row.created_at,
        )

    def delete_classification(self, document_id: str) -> bool:
        deleted, _ = orm.ClassificationModel.objects.filter(document_id=document_id).delete()
        return deleted > 0

    def get_documents_by_type(self, document_type_id: str) -> list[str]:
        return list(
            orm.ClassificationModel.objects.filter(document_type_id=document_type_id).values_list(
                "document_id", flat=True
            )
        )

    def save_extraction_result(self, result) -> None:
        fields_data = [
            {
                "field_name": field.field_name,
                "value": field.value,
                "confidence": field.confidence,
                "source_text": field.source_text,
            }
            for field in result.fields
        ]
        request_logs_data = [
            {
                "request_id": request.request_id,
                "schema_version_id": request.schema_version_id,
                "prompt_version_id": request.prompt_version_id,
                "model": request.model,
                "latency_ms": request.latency_ms,
                "prompt_tokens": request.prompt_tokens,
                "completion_tokens": request.completion_tokens,
                "total_tokens": request.total_tokens,
                "cost_usd": request.cost_usd,
                "cost_note": request.cost_note,
                "created_at": self._iso(request.created_at),
            }
            for request in (getattr(result, "requests", None) or [])
        ]
        request_metadata = dict(getattr(result, "request_metadata", None) or {})

        existing = orm.ExtractionModel.objects.filter(document_id=result.document_id).first()
        if existing:
            existing_logs = existing.request_logs if isinstance(existing.request_logs, list) else []
            combined_logs = [*existing_logs, *request_logs_data]
            # Keep the latest 200 requests per document to cap payload growth.
            combined_logs = combined_logs[-200:]

            existing.document_type_id = result.document_type_id
            existing.schema_version_id = result.schema_version_id
            existing.prompt_version_id = result.prompt_version_id
            existing.extracted_data = fields_data
            existing.request_metadata = request_metadata
            existing.request_logs = combined_logs
            existing.extracted_at = result.extracted_at
            existing.save(
                update_fields=[
                    "document_type_id",
                    "schema_version_id",
                    "prompt_version_id",
                    "extracted_data",
                    "request_metadata",
                    "request_logs",
                    "extracted_at",
                ]
            )
            return

        orm.ExtractionModel.objects.create(
            id=str(uuid4()),
            document_id=result.document_id,
            document_type_id=result.document_type_id,
            schema_version_id=result.schema_version_id,
            prompt_version_id=result.prompt_version_id,
            extracted_data=fields_data,
            request_metadata=request_metadata,
            request_logs=request_logs_data,
            extracted_at=result.extracted_at,
        )

    def get_extraction(self, document_id: str) -> dict[str, Any] | None:
        row = orm.ExtractionModel.objects.filter(document_id=document_id).first()
        if not row:
            return None

        return {
            "id": row.id,
            "document_id": row.document_id,
            "document_type_id": row.document_type_id,
            "schema_version_id": row.schema_version_id,
            "prompt_version_id": row.prompt_version_id,
            "fields": row.extracted_data or [],
            "request_metadata": row.request_metadata or {},
            "requests": row.request_logs or [],
            "extracted_at": self._iso(row.extracted_at),
        }

    def delete_extraction(self, document_id: str) -> bool:
        deleted, _ = orm.ExtractionModel.objects.filter(document_id=document_id).delete()
        return deleted > 0

    def get_prompt_version(self, version_id: str) -> PromptVersion | None:
        row = orm.PromptVersionModel.objects.filter(id=version_id).first()
        return self._prompt_version_from_model(row) if row else None

    @transaction.atomic
    def create_field_prompt_version(self, field_prompt_version: FieldPromptVersion) -> str:
        version_name = self._next_field_prompt_version_name(
            field_prompt_version.document_type_id,
            field_prompt_version.field_name,
        )

        if field_prompt_version.is_active:
            orm.FieldPromptVersionModel.objects.filter(
                document_type_id=field_prompt_version.document_type_id,
                field_name=field_prompt_version.field_name,
            ).update(is_active=False)

        orm.FieldPromptVersionModel.objects.create(
            id=field_prompt_version.id,
            name=version_name,
            document_type_id=field_prompt_version.document_type_id,
            field_name=field_prompt_version.field_name,
            extraction_prompt=field_prompt_version.extraction_prompt,
            description=field_prompt_version.description,
            is_active=bool(field_prompt_version.is_active),
            created_by=field_prompt_version.created_by,
            created_at=field_prompt_version.created_at,
        )
        return field_prompt_version.id

    def get_field_prompt_version(self, version_id: str) -> FieldPromptVersion | None:
        row = orm.FieldPromptVersionModel.objects.filter(id=version_id).first()
        return self._field_prompt_version_from_model(row) if row else None

    def get_active_field_prompt_version(
        self, document_type_id: str, field_name: str
    ) -> FieldPromptVersion | None:
        row = (
            orm.FieldPromptVersionModel.objects.filter(
                is_active=True,
                document_type_id=document_type_id,
                field_name=field_name,
            )
            .order_by("-created_at")
            .first()
        )
        return self._field_prompt_version_from_model(row) if row else None

    def list_active_field_prompt_versions(self, document_type_id: str) -> dict[str, str]:
        rows = (
            orm.FieldPromptVersionModel.objects.filter(
                is_active=True, document_type_id=document_type_id
            )
            .order_by("-created_at")
            .values("field_name", "extraction_prompt")
        )
        prompts_by_field: dict[str, str] = {}
        for row in rows:
            field_name = row["field_name"]
            if field_name not in prompts_by_field:
                prompts_by_field[field_name] = row["extraction_prompt"]
        return prompts_by_field

    def list_active_field_prompt_version_names(self, document_type_id: str) -> dict[str, str]:
        rows = (
            orm.FieldPromptVersionModel.objects.filter(
                is_active=True, document_type_id=document_type_id
            )
            .order_by("-created_at")
            .values("field_name", "name")
        )
        versions_by_field: dict[str, str] = {}
        for row in rows:
            field_name = row["field_name"]
            if field_name not in versions_by_field:
                versions_by_field[field_name] = row["name"]
        return versions_by_field

    def list_active_field_prompt_version_timestamps(self, document_type_id: str) -> dict[str, str]:
        rows = (
            orm.FieldPromptVersionModel.objects.filter(
                is_active=True, document_type_id=document_type_id
            )
            .order_by("-created_at")
            .values("field_name", "created_at")
        )
        timestamps_by_field: dict[str, str] = {}
        for row in rows:
            field_name = row["field_name"]
            if field_name not in timestamps_by_field:
                timestamps_by_field[field_name] = self._iso(row["created_at"]) or ""
        return timestamps_by_field

    def list_field_prompt_versions(
        self,
        document_type_id: str | None = None,
        field_name: str | None = None,
        is_active: bool | None = None,
    ) -> list[FieldPromptVersion]:
        query = orm.FieldPromptVersionModel.objects.all()
        if document_type_id is not None:
            query = query.filter(document_type_id=document_type_id)
        if field_name is not None:
            query = query.filter(field_name=field_name)
        if is_active is not None:
            query = query.filter(is_active=is_active)

        rows = query.order_by("-created_at")
        return [self._field_prompt_version_from_model(row) for row in rows]

    @transaction.atomic
    def update_field_prompt_version(self, version_id: str, updates: dict[str, Any]) -> bool:
        row = orm.FieldPromptVersionModel.objects.filter(id=version_id).first()
        if not row:
            return False

        if updates.get("is_active"):
            orm.FieldPromptVersionModel.objects.filter(
                document_type_id=row.document_type_id,
                field_name=row.field_name,
            ).exclude(id=version_id).update(is_active=False)

        changed_fields: list[str] = []
        for key, value in updates.items():
            setattr(row, key, value)
            changed_fields.append(key)

        if not changed_fields:
            return False

        row.save(update_fields=changed_fields)
        return True

    def delete_field_prompt_version(self, version_id: str) -> bool:
        deleted, _ = orm.FieldPromptVersionModel.objects.filter(id=version_id).delete()
        return deleted > 0

    # Ground Truth Annotation Methods

    def _ground_truth_annotation_from_model(self, model: orm.GroundTruthAnnotationModel):
        from uu_backend.models.annotation import AnnotationType, GroundTruthAnnotation

        return GroundTruthAnnotation(
            id=model.id,
            document_id=model.document_id,
            field_name=model.field_name,
            value=model.value,
            annotation_type=AnnotationType(model.annotation_type),
            annotation_data=model.annotation_data,
            confidence=model.confidence,
            labeled_by=model.labeled_by,
            is_approved=model.is_approved,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def save_ground_truth_annotation(self, annotation_data: dict[str, Any]) -> str:
        annotation_id = annotation_data.get("id") or str(uuid4())

        orm.GroundTruthAnnotationModel.objects.update_or_create(
            id=annotation_id,
            defaults={
                "document_id": annotation_data["document_id"],
                "field_name": annotation_data["field_name"],
                "value": annotation_data["value"],
                "annotation_type": annotation_data["annotation_type"],
                "annotation_data": annotation_data["annotation_data"],
                "confidence": annotation_data.get("confidence", 1.0),
                "labeled_by": annotation_data.get("labeled_by", "manual"),
                "is_approved": annotation_data.get("is_approved", False),
            },
        )

        return annotation_id

    def get_ground_truth_annotation(self, annotation_id: str):
        model = orm.GroundTruthAnnotationModel.objects.filter(id=annotation_id).first()
        return self._ground_truth_annotation_from_model(model) if model else None

    def get_ground_truth_annotations(self, document_id: str) -> list:
        models = orm.GroundTruthAnnotationModel.objects.filter(document_id=document_id).order_by(
            "created_at"
        )

        return [self._ground_truth_annotation_from_model(model) for model in models]

    def get_ground_truth_by_field(self, document_id: str, field_name: str) -> list:
        models = orm.GroundTruthAnnotationModel.objects.filter(
            document_id=document_id, field_name=field_name
        ).order_by("created_at")

        return [self._ground_truth_annotation_from_model(model) for model in models]

    def update_ground_truth_annotation(self, annotation_id: str, updates: dict[str, Any]) -> bool:
        model = orm.GroundTruthAnnotationModel.objects.filter(id=annotation_id).first()
        if not model:
            return False

        changed_fields = []
        for key, value in updates.items():
            if hasattr(model, key) and value is not None:
                setattr(model, key, value)
                changed_fields.append(key)

        if changed_fields:
            model.save(update_fields=changed_fields)
            return True

        return False

    def delete_ground_truth_annotation(self, annotation_id: str) -> bool:
        deleted, _ = orm.GroundTruthAnnotationModel.objects.filter(id=annotation_id).delete()
        return deleted > 0

    def approve_annotation(self, annotation_id: str, edited_value: Any | None = None) -> bool:
        model = orm.GroundTruthAnnotationModel.objects.filter(id=annotation_id).first()
        if not model:
            return False

        update_fields = ["is_approved", "labeled_by"]
        model.is_approved = True
        model.labeled_by = "ai-approved"

        if edited_value is not None:
            model.value = edited_value
            update_fields.append("value")

        model.save(update_fields=update_fields)
        return True
