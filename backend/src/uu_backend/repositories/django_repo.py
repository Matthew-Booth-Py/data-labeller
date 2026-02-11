"""Django ORM-backed repository adapter (no SQLite fallback)."""

import os
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

import django
from django.apps import apps
from django.db import connection
from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uu_backend.django_project.settings.local")
if not apps.ready:
    django.setup()

from uu_backend.django_data import models as orm
from uu_backend.models.annotation import Annotation, AnnotationCreate, AnnotationType, Label, LabelCreate
from uu_backend.models.evaluation import (
    ExtractionEvaluation,
    ExtractionEvaluationMetrics,
    FieldPromptVersion,
    PromptVersion,
)
from uu_backend.models.feedback import Feedback, FeedbackCreate, FeedbackSource, FeedbackType, TrainingStatus
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
    """Repository adapter backed by Django ORM models."""

    @staticmethod
    def _parse_incremental_version(name: Optional[str]) -> Optional[int]:
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
    def _iso(value: Optional[datetime]) -> Optional[str]:
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
            extraction_model=model.extraction_model,
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
            extraction_model=model.extraction_model,
            ocr_engine=model.ocr_engine,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    def _label_from_model(self, model: orm.LabelModel) -> Label:
        return Label(
            id=model.id,
            name=model.name,
            color=model.color,
            description=model.description,
            shortcut=model.shortcut,
            entity_type=model.entity_type,
            document_type_id=model.document_type_id,
        )

    def _annotation_from_model(
        self,
        model: orm.AnnotationModel,
        labels_by_id: Optional[dict[str, orm.LabelModel]] = None,
    ) -> Annotation:
        label = (labels_by_id or {}).get(model.label_id)
        metadata = model.metadata or {}
        return Annotation(
            id=model.id,
            document_id=model.document_id,
            label_id=model.label_id,
            label_name=(label.name if label else None),
            label_color=(label.color if label else None),
            annotation_type=AnnotationType(model.annotation_type),
            start_offset=model.start_offset,
            end_offset=model.end_offset,
            text=model.text,
            page=model.page,
            x=model.x,
            y=model.y,
            width=model.width,
            height=model.height,
            key_text=model.key_text,
            key_start=model.key_start,
            key_end=model.key_end,
            value_text=model.value_text,
            value_start=model.value_start,
            value_end=model.value_end,
            entity_type=model.entity_type,
            normalized_value=model.normalized_value,
            row_index=model.row_index,
            group_id=model.group_id,
            metadata=(metadata or None),
            created_by=model.created_by,
            created_at=model.created_at,
        )

    def _feedback_from_model(self, model: orm.FeedbackModel, with_embeddings: bool = False) -> Feedback:
        return Feedback(
            id=model.id,
            document_id=model.document_id,
            label_id=model.label_id,
            label_name=model.label_name,
            text=model.text,
            start_offset=model.start_offset,
            end_offset=model.end_offset,
            feedback_type=FeedbackType(model.feedback_type),
            source=FeedbackSource(model.source),
            embedding=(model.embedding if with_embeddings else None),
            created_at=model.created_at,
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

    def _field_prompt_version_from_model(self, model: orm.FieldPromptVersionModel) -> FieldPromptVersion:
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

    def _evaluation_from_model(self, model: orm.EvaluationModel) -> ExtractionEvaluation:
        prompt_name = None
        if model.prompt_version_id:
            prompt_name = (
                orm.PromptVersionModel.objects.filter(id=model.prompt_version_id)
                .values_list("name", flat=True)
                .first()
            )

        metrics_payload = model.metrics or {}
        metrics = ExtractionEvaluationMetrics.model_validate(metrics_payload)

        return ExtractionEvaluation(
            id=model.id,
            document_id=model.document_id,
            document_type_id=model.document_type_id,
            prompt_version_id=model.prompt_version_id,
            prompt_version_name=prompt_name,
            field_prompt_versions=model.field_prompt_versions or {},
            schema_version_id=model.schema_version_id,
            metrics=metrics,
            extraction_time_ms=model.extraction_time_ms,
            evaluated_by=model.evaluated_by,
            evaluated_at=model.evaluated_at,
            notes=model.notes,
        )

    def _next_prompt_version_name(self, document_type_id: Optional[str]) -> str:
        query = orm.PromptVersionModel.objects.all()
        if document_type_id is None:
            query = query.filter(document_type_id__isnull=True)
        else:
            query = query.filter(document_type_id=document_type_id)

        minors = [
            parsed
            for parsed in (self._parse_incremental_version(name) for name in query.values_list("name", flat=True))
            if parsed is not None
        ]
        next_minor = (max(minors) + 1) if minors else 0
        return self._format_incremental_version(next_minor)

    def _next_field_prompt_version_name(self, document_type_id: str, field_name: str) -> str:
        query = orm.FieldPromptVersionModel.objects.filter(
            document_type_id=document_type_id,
            field_name=field_name,
        )
        minors = [
            parsed
            for parsed in (self._parse_incremental_version(name) for name in query.values_list("name", flat=True))
            if parsed is not None
        ]
        next_minor = (max(minors) + 1) if minors else 0
        return self._format_incremental_version(next_minor)

    def _next_deployment_version_name(self, project_id: str) -> str:
        query = orm.DeploymentVersionModel.objects.filter(project_id=project_id)
        minors = [
            parsed
            for parsed in (self._parse_incremental_version(name) for name in query.values_list("version", flat=True))
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
            extraction_model=data.extraction_model or "gpt-5-mini",
            ocr_engine=data.ocr_engine or "azure-di-prebuilt",
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
            extraction_model=data.extraction_model or "gpt-5-mini",
            ocr_engine=data.ocr_engine or "azure-di-prebuilt",
            created_at=now,
            created_by=None,
        )

        return self._document_type_from_model(row)

    def get_document_type(self, type_id: str) -> Optional[DocumentType]:
        row = orm.DocumentTypeModel.objects.filter(id=type_id).first()
        return self._document_type_from_model(row) if row else None

    def get_document_type_by_name(self, name: str) -> Optional[DocumentType]:
        row = orm.DocumentTypeModel.objects.filter(name=name).first()
        return self._document_type_from_model(row) if row else None

    def list_document_types(self) -> list[DocumentType]:
        rows = orm.DocumentTypeModel.objects.order_by("name")
        return [self._document_type_from_model(row) for row in rows]

    @transaction.atomic
    def update_document_type(self, type_id: str, data: DocumentTypeUpdate) -> Optional[DocumentType]:
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
        if data.extraction_model is not None:
            updates["extraction_model"] = data.extraction_model
        if data.ocr_engine is not None:
            updates["ocr_engine"] = data.ocr_engine

        requires_new_schema_version = any(
            key in updates
            for key in ("schema_fields", "system_prompt", "post_processing", "extraction_model", "ocr_engine")
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
            next_extraction_model = updates.get("extraction_model", existing.extraction_model)
            next_ocr_engine = updates.get("ocr_engine", existing.ocr_engine)

            orm.SchemaVersionModel.objects.create(
                id=schema_version_id,
                document_type_id=type_id,
                schema_fields=next_schema_fields,
                system_prompt=next_system_prompt,
                post_processing=next_post_processing,
                extraction_model=next_extraction_model,
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
        rows = orm.SchemaVersionModel.objects.filter(document_type_id=document_type_id).order_by("-created_at")
        return [
            {
                "id": row.id,
                "document_type_id": row.document_type_id,
                "schema_fields": row.schema_fields or [],
                "system_prompt": row.system_prompt,
                "post_processing": row.post_processing,
                "extraction_model": row.extraction_model,
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
        prompt_version_id: Optional[str] = None,
        created_by: Optional[str] = None,
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

        created = orm.DeploymentVersionModel.objects.create(
            id=deployment_id,
            project_id=project_id,
            version=version,
            document_type_id=document_type_id,
            document_type_name=doc_type.name,
            schema_version_id=doc_type.schema_version_id,
            prompt_version_id=prompt_version_id,
            system_prompt=(prompt_version.system_prompt if prompt_version else doc_type.system_prompt),
            user_prompt_template=(prompt_version.user_prompt_template if prompt_version else None),
            schema_fields=snapshot_schema_fields,
            field_prompt_versions=active_field_prompt_versions,
            model=doc_type.extraction_model or "gpt-5-mini",
            is_active=set_active,
            created_by=created_by,
            created_at=now,
        )

        return self._deployment_from_model(created)

    def get_deployment_version(self, deployment_version_id: str) -> Optional[dict[str, Any]]:
        row = orm.DeploymentVersionModel.objects.filter(id=deployment_version_id).first()
        return self._deployment_from_model(row) if row else None

    def get_deployment_version_by_name(self, project_id: str, version: str) -> Optional[dict[str, Any]]:
        row = orm.DeploymentVersionModel.objects.filter(project_id=project_id, version=version).first()
        return self._deployment_from_model(row) if row else None

    def list_deployment_versions(self, project_id: str) -> list[dict[str, Any]]:
        rows = orm.DeploymentVersionModel.objects.filter(project_id=project_id).order_by("-created_at", "-id")
        return [self._deployment_from_model(row) for row in rows]

    def get_active_deployment_version(self, project_id: str) -> Optional[dict[str, Any]]:
        row = (
            orm.DeploymentVersionModel.objects.filter(project_id=project_id, is_active=True)
            .order_by("-created_at", "-id")
            .first()
        )
        return self._deployment_from_model(row) if row else None

    @transaction.atomic
    def activate_deployment_version(self, project_id: str, deployment_version_id: str) -> Optional[dict[str, Any]]:
        row = orm.DeploymentVersionModel.objects.filter(id=deployment_version_id, project_id=project_id).first()
        if not row:
            return None

        orm.DeploymentVersionModel.objects.filter(project_id=project_id).update(is_active=False)
        row.is_active = True
        row.save(update_fields=["is_active"])
        return self._deployment_from_model(row)

    def get_llm_provider_settings(self, provider: str) -> Optional[dict[str, Any]]:
        row = orm.LLMProviderSettingsModel.objects.filter(provider=provider).first()
        if not row:
            return None
        return {
            "provider": row.provider,
            "api_key_override": row.api_key_override,
            "last_test_status": row.last_test_status,
            "last_tested_at": self._iso(row.last_tested_at),
            "updated_at": self._iso(row.updated_at),
        }

    def upsert_llm_provider_api_key(self, provider: str, api_key_override: Optional[str]) -> dict[str, Any]:
        now = timezone.now()
        orm.LLMProviderSettingsModel.objects.update_or_create(
            provider=provider,
            defaults={
                "api_key_override": api_key_override,
                "updated_at": now,
            },
        )
        return self.get_llm_provider_settings(provider) or {
            "provider": provider,
            "api_key_override": api_key_override,
            "last_test_status": "unknown",
            "last_tested_at": None,
            "updated_at": self._iso(now),
        }

    def update_llm_provider_test_status(self, provider: str, status: str) -> dict[str, Any]:
        now = timezone.now()
        orm.LLMProviderSettingsModel.objects.update_or_create(
            provider=provider,
            defaults={
                "last_test_status": status,
                "last_tested_at": now,
                "updated_at": now,
            },
        )
        return self.get_llm_provider_settings(provider) or {
            "provider": provider,
            "api_key_override": None,
            "last_test_status": status,
            "last_tested_at": self._iso(now),
            "updated_at": self._iso(now),
        }

    def list_llm_provider_models(self, provider: str, enabled_only: bool = False) -> list[dict[str, Any]]:
        query = orm.LLMProviderModelModel.objects.filter(provider=provider)
        if enabled_only:
            query = query.filter(is_enabled=True)
        rows = query.order_by("model_id")
        return [
            {
                "provider": row.provider,
                "model_id": row.model_id,
                "display_name": row.display_name,
                "is_enabled": bool(row.is_enabled),
                "created_at": self._iso(row.created_at) or "",
                "updated_at": self._iso(row.updated_at) or "",
            }
            for row in rows
        ]

    def upsert_llm_provider_model(
        self,
        provider: str,
        model_id: str,
        display_name: Optional[str] = None,
        is_enabled: bool = True,
    ) -> dict[str, Any]:
        now = timezone.now()
        row = orm.LLMProviderModelModel.objects.filter(provider=provider, model_id=model_id).first()
        if row:
            if display_name is not None:
                row.display_name = display_name
            row.is_enabled = is_enabled
            row.updated_at = now
            row.save(update_fields=["display_name", "is_enabled", "updated_at"])
        else:
            row = orm.LLMProviderModelModel.objects.create(
                id=f"{provider}::{model_id}",
                provider=provider,
                model_id=model_id,
                display_name=display_name,
                is_enabled=is_enabled,
                created_at=now,
                updated_at=now,
            )

        return {
            "provider": row.provider,
            "model_id": row.model_id,
            "display_name": row.display_name,
            "is_enabled": bool(row.is_enabled),
            "created_at": self._iso(row.created_at) or "",
            "updated_at": self._iso(row.updated_at) or "",
        }

    def update_llm_provider_model(
        self,
        provider: str,
        model_id: str,
        display_name: Optional[str] = None,
        is_enabled: Optional[bool] = None,
    ) -> Optional[dict[str, Any]]:
        row = orm.LLMProviderModelModel.objects.filter(provider=provider, model_id=model_id).first()
        if not row:
            return None

        changed_fields: list[str] = []
        if display_name is not None:
            row.display_name = display_name
            changed_fields.append("display_name")
        if is_enabled is not None:
            row.is_enabled = is_enabled
            changed_fields.append("is_enabled")

        if changed_fields:
            row.updated_at = timezone.now()
            changed_fields.append("updated_at")
            row.save(update_fields=changed_fields)

        return {
            "provider": row.provider,
            "model_id": row.model_id,
            "display_name": row.display_name,
            "is_enabled": bool(row.is_enabled),
            "created_at": self._iso(row.created_at) or "",
            "updated_at": self._iso(row.updated_at) or "",
        }

    def delete_llm_provider_model(self, provider: str, model_id: str) -> bool:
        deleted, _ = orm.LLMProviderModelModel.objects.filter(provider=provider, model_id=model_id).delete()
        return deleted > 0

    def create_global_field(self, data: GlobalFieldCreate) -> GlobalField:
        now = timezone.now()
        row = orm.GlobalFieldModel.objects.create(
            id=str(uuid4()),
            name=data.name,
            type=data.type.value,
            prompt=data.prompt,
            description=data.description,
            extraction_model=data.extraction_model or "gpt-5-mini",
            ocr_engine=data.ocr_engine or "azure-di-prebuilt",
            created_by=data.created_by,
            created_at=now,
            updated_at=now,
        )
        return self._global_field_from_model(row)

    def list_global_fields(self, search: Optional[str] = None) -> list[GlobalField]:
        query = orm.GlobalFieldModel.objects.all()
        if search:
            query = query.filter(Q(name__icontains=search) | Q(prompt__icontains=search) | Q(description__icontains=search))
        rows = query.order_by("name")
        return [self._global_field_from_model(row) for row in rows]

    def get_global_field(self, field_id: str) -> Optional[GlobalField]:
        row = orm.GlobalFieldModel.objects.filter(id=field_id).first()
        return self._global_field_from_model(row) if row else None

    def get_global_field_by_name(self, name: str) -> Optional[GlobalField]:
        row = orm.GlobalFieldModel.objects.filter(name=name).first()
        return self._global_field_from_model(row) if row else None

    def update_global_field(self, field_id: str, data: GlobalFieldUpdate) -> Optional[GlobalField]:
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
        if data.extraction_model is not None:
            row.extraction_model = data.extraction_model
            changed_fields.append("extraction_model")
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
        confidence: Optional[float] = None,
        labeled_by: Optional[str] = None,
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

    def get_classification(self, document_id: str) -> Optional[Classification]:
        row = orm.ClassificationModel.objects.filter(document_id=document_id).first()
        if not row:
            return None

        doc_type_name = (
            orm.DocumentTypeModel.objects.filter(id=row.document_type_id).values_list("name", flat=True).first()
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
            orm.ClassificationModel.objects.filter(document_type_id=document_type_id).values_list("document_id", flat=True)
        )

    def create_label(self, data: LabelCreate) -> Label:
        row = orm.LabelModel.objects.create(
            id=str(uuid4()),
            name=data.name,
            color=data.color,
            description=data.description,
            shortcut=data.shortcut,
            entity_type=data.entity_type,
            document_type_id=data.document_type_id,
            created_at=timezone.now(),
        )
        return self._label_from_model(row)

    def get_label(self, label_id: str) -> Optional[Label]:
        row = orm.LabelModel.objects.filter(id=label_id).first()
        return self._label_from_model(row) if row else None

    def get_label_by_name(self, name: str) -> Optional[Label]:
        row = orm.LabelModel.objects.filter(name=name).first()
        return self._label_from_model(row) if row else None

    def list_labels(self, document_type_id: Optional[str] = None, include_global: bool = True) -> list[Label]:
        query = orm.LabelModel.objects.all()
        if document_type_id:
            if include_global:
                query = query.filter(Q(document_type_id=document_type_id) | Q(document_type_id__isnull=True))
            else:
                query = query.filter(document_type_id=document_type_id)

        rows = query.order_by("name")
        return [self._label_from_model(row) for row in rows]

    @transaction.atomic
    def delete_label(self, label_id: str) -> bool:
        orm.AnnotationModel.objects.filter(label_id=label_id).delete()
        deleted, _ = orm.LabelModel.objects.filter(id=label_id).delete()
        return deleted > 0

    def create_annotation(self, document_id: str, data: AnnotationCreate) -> Annotation:
        label = orm.LabelModel.objects.filter(id=data.label_id).first()
        if not label:
            raise ValueError(f"Label {data.label_id} not found")

        row = orm.AnnotationModel.objects.create(
            id=str(uuid4()),
            document_id=document_id,
            label_id=data.label_id,
            annotation_type=data.annotation_type.value,
            start_offset=data.start_offset,
            end_offset=data.end_offset,
            text=data.text,
            page=data.page,
            x=data.x,
            y=data.y,
            width=data.width,
            height=data.height,
            key_text=data.key_text,
            key_start=data.key_start,
            key_end=data.key_end,
            value_text=data.value_text,
            value_start=data.value_start,
            value_end=data.value_end,
            entity_type=data.entity_type,
            normalized_value=data.normalized_value,
            row_index=data.row_index,
            group_id=data.group_id,
            metadata=data.metadata or {},
            created_by=data.created_by,
            created_at=timezone.now(),
        )
        return self._annotation_from_model(row, labels_by_id={label.id: label})

    def get_annotation(self, annotation_id: str) -> Optional[Annotation]:
        row = orm.AnnotationModel.objects.filter(id=annotation_id).first()
        if not row:
            return None
        label = orm.LabelModel.objects.filter(id=row.label_id).first()
        labels_by_id = {label.id: label} if label else {}
        return self._annotation_from_model(row, labels_by_id=labels_by_id)

    def list_annotations(
        self,
        document_id: str,
        annotation_type: Optional[AnnotationType] = None,
        label_id: Optional[str] = None,
    ) -> list[Annotation]:
        query = orm.AnnotationModel.objects.filter(document_id=document_id)
        if annotation_type:
            query = query.filter(annotation_type=annotation_type.value)
        if label_id:
            query = query.filter(label_id=label_id)

        rows = list(query.order_by("-created_at"))
        label_ids = {row.label_id for row in rows}
        labels_by_id = {
            row.id: row
            for row in orm.LabelModel.objects.filter(id__in=label_ids)
        }
        return [self._annotation_from_model(row, labels_by_id=labels_by_id) for row in rows]

    def delete_annotation(self, annotation_id: str) -> bool:
        deleted, _ = orm.AnnotationModel.objects.filter(id=annotation_id).delete()
        return deleted > 0

    def delete_document_annotations(self, document_id: str) -> int:
        deleted, _ = orm.AnnotationModel.objects.filter(document_id=document_id).delete()
        return int(deleted)

    def get_annotation_stats(self, document_id: str) -> dict[str, Any]:
        total = orm.AnnotationModel.objects.filter(document_id=document_id).count()

        by_type_rows = (
            orm.AnnotationModel.objects.filter(document_id=document_id)
            .values("annotation_type")
            .annotate(count=Count("id"))
        )
        by_type = {row["annotation_type"]: row["count"] for row in by_type_rows}

        label_counts = (
            orm.AnnotationModel.objects.filter(document_id=document_id)
            .values("label_id")
            .annotate(count=Count("id"))
        )
        labels = {
            row.id: row.name
            for row in orm.LabelModel.objects.filter(id__in=[entry["label_id"] for entry in label_counts])
        }
        by_label = {labels.get(row["label_id"], "Unknown"): row["count"] for row in label_counts}

        return {
            "document_id": document_id,
            "total_annotations": total,
            "by_type": by_type,
            "by_label": by_label,
        }

    def create_feedback(self, data: FeedbackCreate, embedding: Optional[list[float]] = None) -> Feedback:
        label = orm.LabelModel.objects.filter(id=data.label_id).first()
        label_name = label.name if label else None

        row = orm.FeedbackModel.objects.create(
            id=str(uuid4()),
            document_id=data.document_id,
            label_id=data.label_id,
            label_name=label_name,
            text=data.text,
            start_offset=data.start_offset,
            end_offset=data.end_offset,
            feedback_type=data.feedback_type.value,
            source=data.source.value,
            embedding=embedding,
            created_at=timezone.now(),
        )
        return self._feedback_from_model(row, with_embeddings=bool(embedding))

    def list_feedback(
        self,
        label_id: Optional[str] = None,
        feedback_type: Optional[FeedbackType] = None,
        with_embeddings: bool = False,
    ) -> list[Feedback]:
        query = orm.FeedbackModel.objects.all()
        if label_id:
            query = query.filter(label_id=label_id)
        if feedback_type:
            query = query.filter(feedback_type=feedback_type.value)
        rows = query.order_by("-created_at")
        return [self._feedback_from_model(row, with_embeddings=with_embeddings) for row in rows]

    def get_feedback_count(self) -> int:
        return orm.FeedbackModel.objects.count()

    def get_positive_feedback(self, with_embeddings: bool = True) -> list[Feedback]:
        rows = orm.FeedbackModel.objects.filter(feedback_type__in=["correct", "accepted"]).order_by("created_at")
        return [self._feedback_from_model(row, with_embeddings=with_embeddings) for row in rows]

    def get_all_training_feedback(self, with_embeddings: bool = True) -> list[Feedback]:
        rows = orm.FeedbackModel.objects.order_by("created_at")
        return [self._feedback_from_model(row, with_embeddings=with_embeddings) for row in rows]

    def get_training_status(self) -> TrainingStatus:
        total = orm.FeedbackModel.objects.count()
        positive = orm.FeedbackModel.objects.filter(feedback_type__in=["correct", "accepted"]).count()
        negative = orm.FeedbackModel.objects.filter(feedback_type__in=["incorrect", "rejected"]).count()
        labels_count = orm.FeedbackModel.objects.values("label_id").distinct().count()
        latest_model = orm.ModelStatusModel.objects.order_by("-trained_at").first()

        min_samples = 20
        return TrainingStatus(
            is_trained=latest_model is not None,
            sample_count=total,
            positive_samples=positive,
            negative_samples=negative,
            labels_count=labels_count,
            last_trained_at=(latest_model.trained_at if latest_model else None),
            accuracy=(latest_model.accuracy if latest_model else None),
            model_path=(latest_model.model_path if latest_model else None),
            min_samples_required=min_samples,
            ready_to_train=positive >= min_samples and labels_count >= 2,
        )

    def save_model_status(
        self,
        sample_count: int,
        positive_samples: int,
        negative_samples: int,
        labels_count: int,
        accuracy: Optional[float],
        model_path: str,
    ) -> None:
        orm.ModelStatusModel.objects.create(
            trained_at=timezone.now(),
            sample_count=sample_count,
            positive_samples=positive_samples,
            negative_samples=negative_samples,
            labels_count=labels_count,
            accuracy=accuracy,
            model_path=model_path,
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

        existing = orm.ExtractionModel.objects.filter(document_id=result.document_id).first()
        if existing:
            existing.document_type_id = result.document_type_id
            existing.schema_version_id = result.schema_version_id
            existing.prompt_version_id = result.prompt_version_id
            existing.extracted_data = fields_data
            existing.extracted_at = result.extracted_at
            existing.save(
                update_fields=[
                    "document_type_id",
                    "schema_version_id",
                    "prompt_version_id",
                    "extracted_data",
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
            extracted_at=result.extracted_at,
        )

    def get_extraction(self, document_id: str) -> Optional[dict[str, Any]]:
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
            "extracted_at": self._iso(row.extracted_at),
        }

    def delete_extraction(self, document_id: str) -> bool:
        deleted, _ = orm.ExtractionModel.objects.filter(document_id=document_id).delete()
        return deleted > 0

    @transaction.atomic
    def create_prompt_version(self, prompt_version: PromptVersion) -> str:
        version_name = self._next_prompt_version_name(prompt_version.document_type_id)

        if prompt_version.is_active:
            query = orm.PromptVersionModel.objects.exclude(id=prompt_version.id)
            if prompt_version.document_type_id is None:
                query = query.filter(document_type_id__isnull=True)
            else:
                query = query.filter(document_type_id=prompt_version.document_type_id)
            query.update(is_active=False)

        orm.PromptVersionModel.objects.create(
            id=prompt_version.id,
            name=version_name,
            document_type_id=prompt_version.document_type_id,
            system_prompt=prompt_version.system_prompt,
            user_prompt_template=prompt_version.user_prompt_template,
            description=prompt_version.description,
            is_active=bool(prompt_version.is_active),
            created_by=prompt_version.created_by,
            created_at=prompt_version.created_at,
        )
        return prompt_version.id

    def get_prompt_version(self, version_id: str) -> Optional[PromptVersion]:
        row = orm.PromptVersionModel.objects.filter(id=version_id).first()
        return self._prompt_version_from_model(row) if row else None

    def get_active_prompt_version(self, document_type_id: Optional[str] = None) -> Optional[PromptVersion]:
        query = orm.PromptVersionModel.objects.filter(is_active=True)
        if document_type_id is None:
            query = query.filter(document_type_id__isnull=True)
        else:
            query = query.filter(document_type_id=document_type_id)
        row = query.order_by("-created_at").first()
        return self._prompt_version_from_model(row) if row else None

    def list_prompt_versions(
        self,
        document_type_id: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> list[PromptVersion]:
        query = orm.PromptVersionModel.objects.all()
        if document_type_id is not None:
            query = query.filter(Q(document_type_id=document_type_id) | Q(document_type_id__isnull=True))
        if is_active is not None:
            query = query.filter(is_active=is_active)
        rows = query.order_by("-created_at")
        return [self._prompt_version_from_model(row) for row in rows]

    @transaction.atomic
    def update_prompt_version(self, version_id: str, updates: dict[str, Any]) -> bool:
        row = orm.PromptVersionModel.objects.filter(id=version_id).first()
        if not row:
            return False

        if updates.get("is_active"):
            query = orm.PromptVersionModel.objects.exclude(id=version_id)
            if row.document_type_id is None:
                query = query.filter(document_type_id__isnull=True)
            else:
                query = query.filter(document_type_id=row.document_type_id)
            query.update(is_active=False)

        changed_fields: list[str] = []
        for key, value in updates.items():
            setattr(row, key, value)
            changed_fields.append(key)

        if not changed_fields:
            return False

        row.save(update_fields=changed_fields)
        return True

    def delete_prompt_version(self, version_id: str) -> bool:
        deleted, _ = orm.PromptVersionModel.objects.filter(id=version_id).delete()
        return deleted > 0

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

    def get_field_prompt_version(self, version_id: str) -> Optional[FieldPromptVersion]:
        row = orm.FieldPromptVersionModel.objects.filter(id=version_id).first()
        return self._field_prompt_version_from_model(row) if row else None

    def get_active_field_prompt_version(self, document_type_id: str, field_name: str) -> Optional[FieldPromptVersion]:
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
            orm.FieldPromptVersionModel.objects.filter(is_active=True, document_type_id=document_type_id)
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
            orm.FieldPromptVersionModel.objects.filter(is_active=True, document_type_id=document_type_id)
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
            orm.FieldPromptVersionModel.objects.filter(is_active=True, document_type_id=document_type_id)
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
        document_type_id: Optional[str] = None,
        field_name: Optional[str] = None,
        is_active: Optional[bool] = None,
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

    def save_evaluation(self, evaluation: ExtractionEvaluation) -> None:
        orm.EvaluationModel.objects.create(
            id=evaluation.id,
            document_id=evaluation.document_id,
            document_type_id=evaluation.document_type_id,
            prompt_version_id=evaluation.prompt_version_id,
            schema_version_id=evaluation.schema_version_id,
            comparator_mode=evaluation.metrics.comparator_mode,
            field_prompt_versions=evaluation.field_prompt_versions or {},
            metrics=evaluation.metrics.model_dump(mode="json"),
            extraction_time_ms=evaluation.extraction_time_ms,
            evaluated_by=evaluation.evaluated_by,
            evaluated_at=evaluation.evaluated_at,
            notes=evaluation.notes,
        )

    def get_evaluation(self, evaluation_id: str) -> Optional[ExtractionEvaluation]:
        row = orm.EvaluationModel.objects.filter(id=evaluation_id).first()
        return self._evaluation_from_model(row) if row else None

    def delete_evaluation(self, evaluation_id: str) -> bool:
        deleted, _ = orm.EvaluationModel.objects.filter(id=evaluation_id).delete()
        return deleted > 0

    def list_evaluations(
        self,
        document_id: Optional[str] = None,
        document_type_id: Optional[str] = None,
        prompt_version_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[ExtractionEvaluation], int]:
        query = orm.EvaluationModel.objects.all()
        if document_id:
            query = query.filter(document_id=document_id)
        if document_type_id:
            query = query.filter(document_type_id=document_type_id)
        if prompt_version_id:
            query = query.filter(prompt_version_id=prompt_version_id)

        total = query.count()
        rows = query.order_by("-evaluated_at")[offset : offset + limit]
        return [self._evaluation_from_model(row) for row in rows], total

    def get_evaluation_summary(
        self,
        prompt_version_id: Optional[str] = None,
        document_type_id: Optional[str] = None,
    ) -> Optional[dict[str, Any] | list[dict[str, Any]]]:
        query = orm.EvaluationModel.objects.all()
        if prompt_version_id:
            query = query.filter(prompt_version_id=prompt_version_id)
        if document_type_id:
            query = query.filter(document_type_id=document_type_id)

        if not query.exists():
            return None

        group_keys = query.values_list("prompt_version_id", "document_type_id").distinct()
        results: list[dict[str, Any]] = []

        for grouped_prompt_version_id, grouped_document_type_id in group_keys:
            grouped = query.filter(
                prompt_version_id=grouped_prompt_version_id,
                document_type_id=grouped_document_type_id,
            )
            rows = list(grouped.order_by("evaluated_at"))
            total = len(rows)
            if total == 0:
                continue

            prompt_name = None
            if grouped_prompt_version_id:
                prompt_name = (
                    orm.PromptVersionModel.objects.filter(id=grouped_prompt_version_id)
                    .values_list("name", flat=True)
                    .first()
                )

            sum_accuracy = 0.0
            sum_precision = 0.0
            sum_recall = 0.0
            sum_f1 = 0.0
            field_stats: dict[str, dict[str, int]] = {}

            for row in rows:
                metrics = ExtractionEvaluationMetrics.model_validate(row.metrics or {})
                sum_accuracy += metrics.accuracy
                sum_precision += metrics.precision
                sum_recall += metrics.recall
                sum_f1 += metrics.f1_score

                for field_eval in metrics.field_evaluations:
                    stats = field_stats.setdefault(
                        field_eval.field_name,
                        {"correct": 0, "total": 0, "present": 0, "extracted": 0},
                    )
                    stats["total"] += 1
                    if field_eval.is_correct:
                        stats["correct"] += 1
                    if field_eval.is_present:
                        stats["present"] += 1
                    if field_eval.is_extracted:
                        stats["extracted"] += 1

            field_performance: dict[str, dict[str, float]] = {}
            for field_name, stats in field_stats.items():
                accuracy = (stats["correct"] / stats["total"]) if stats["total"] > 0 else 0.0
                precision = (stats["correct"] / stats["extracted"]) if stats["extracted"] > 0 else 0.0
                recall = (stats["correct"] / stats["present"]) if stats["present"] > 0 else 0.0
                field_performance[field_name] = {
                    "accuracy": accuracy,
                    "precision": precision,
                    "recall": recall,
                }

            earliest = min(row.evaluated_at for row in rows)
            latest = max(row.evaluated_at for row in rows)

            results.append(
                {
                    "prompt_version_id": grouped_prompt_version_id,
                    "prompt_version_name": prompt_name,
                    "document_type_id": grouped_document_type_id,
                    "total_evaluations": total,
                    "avg_accuracy": sum_accuracy / total,
                    "avg_precision": sum_precision / total,
                    "avg_recall": sum_recall / total,
                    "avg_f1_score": sum_f1 / total,
                    "field_performance": field_performance,
                    "earliest_evaluation": self._iso(earliest),
                    "latest_evaluation": self._iso(latest),
                }
            )

        if len(results) == 1:
            return results[0]
        return results

    def create_benchmark_dataset(self, data: dict[str, Any]) -> dict[str, Any]:
        now = timezone.now()
        row = orm.BenchmarkDatasetModel.objects.create(
            id=str(uuid4()),
            name=data["name"],
            document_type_id=data["document_type_id"],
            description=data.get("description"),
            created_by=data.get("created_by"),
            created_at=now,
        )
        return {
            "id": row.id,
            "name": row.name,
            "document_type_id": row.document_type_id,
            "description": row.description,
            "created_by": row.created_by,
            "created_at": row.created_at,
        }

    def add_benchmark_dataset_document(
        self,
        dataset_id: str,
        document_id: str,
        split: str = "test",
        tags: Optional[list[str]] = None,
        doc_subtype: Optional[str] = None,
    ) -> dict[str, Any]:
        row = orm.BenchmarkDatasetDocumentModel.objects.filter(
            dataset_id=dataset_id,
            document_id=document_id,
        ).first()
        if row:
            row.split = split
            row.tags = tags or []
            row.doc_subtype = doc_subtype
            row.save(update_fields=["split", "tags", "doc_subtype"])
        else:
            row = orm.BenchmarkDatasetDocumentModel.objects.create(
                id=str(uuid4()),
                dataset_id=dataset_id,
                document_id=document_id,
                split=split,
                tags=tags or [],
                doc_subtype=doc_subtype,
                created_at=timezone.now(),
            )

        return {
            "document_id": row.document_id,
            "split": row.split,
            "tags": row.tags or [],
            "doc_subtype": row.doc_subtype,
        }

    def list_benchmark_datasets(self, document_type_id: Optional[str] = None) -> list[dict[str, Any]]:
        query = orm.BenchmarkDatasetModel.objects.all()
        if document_type_id:
            query = query.filter(document_type_id=document_type_id)

        rows = query.order_by("-created_at")
        return [
            {
                "id": row.id,
                "name": row.name,
                "document_type_id": row.document_type_id,
                "description": row.description,
                "created_by": row.created_by,
                "created_at": row.created_at,
            }
            for row in rows
        ]

    def get_benchmark_dataset(self, dataset_id: str) -> Optional[dict[str, Any]]:
        row = orm.BenchmarkDatasetModel.objects.filter(id=dataset_id).first()
        if not row:
            return None

        doc_rows = orm.BenchmarkDatasetDocumentModel.objects.filter(dataset_id=dataset_id).order_by("created_at")
        documents = [
            {
                "document_id": item.document_id,
                "split": item.split,
                "tags": item.tags or [],
                "doc_subtype": item.doc_subtype,
            }
            for item in doc_rows
        ]

        return {
            "id": row.id,
            "name": row.name,
            "document_type_id": row.document_type_id,
            "description": row.description,
            "created_by": row.created_by,
            "created_at": row.created_at,
            "documents": documents,
        }

    def save_benchmark_run(self, run: dict[str, Any]) -> None:
        orm.BenchmarkRunModel.objects.create(
            id=run["id"],
            dataset_id=run["dataset_id"],
            document_type_id=run["document_type_id"],
            prompt_version_id=run.get("prompt_version_id"),
            baseline_run_id=run.get("baseline_run_id"),
            total_documents=run["total_documents"],
            successful_documents=run["successful_documents"],
            failed_documents=run["failed_documents"],
            overall_metrics=run["overall_metrics"],
            split_metrics=run["split_metrics"],
            subtype_scorecards=run["subtype_scorecards"],
            confidence_intervals=run["confidence_intervals"],
            drift_delta=run.get("drift_delta"),
            gate_results=run.get("gate_results", []),
            passed_gates=run.get("passed_gates", True),
            errors=run.get("errors", []),
            use_llm_refinement=run.get("use_llm_refinement", True),
            use_structured_output=run.get("use_structured_output", False),
            evaluated_by=run.get("evaluated_by"),
            notes=run.get("notes"),
            created_at=run["created_at"],
        )

    def get_benchmark_run(self, run_id: str) -> Optional[dict[str, Any]]:
        row = orm.BenchmarkRunModel.objects.filter(id=run_id).first()
        if not row:
            return None

        return {
            "id": row.id,
            "dataset_id": row.dataset_id,
            "document_type_id": row.document_type_id,
            "prompt_version_id": row.prompt_version_id,
            "baseline_run_id": row.baseline_run_id,
            "total_documents": row.total_documents,
            "successful_documents": row.successful_documents,
            "failed_documents": row.failed_documents,
            "overall_metrics": row.overall_metrics or {},
            "split_metrics": row.split_metrics or {},
            "subtype_scorecards": row.subtype_scorecards or {},
            "confidence_intervals": row.confidence_intervals or {},
            "drift_delta": row.drift_delta,
            "gate_results": row.gate_results or [],
            "passed_gates": bool(row.passed_gates),
            "errors": row.errors or [],
            "use_llm_refinement": bool(row.use_llm_refinement),
            "use_structured_output": bool(row.use_structured_output),
            "evaluated_by": row.evaluated_by,
            "notes": row.notes,
            "created_at": row.created_at,
        }
