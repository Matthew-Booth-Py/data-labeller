"""DRF views for taxonomy and extraction endpoints."""

import json

from asgiref.sync import async_to_sync
from django.db import IntegrityError
from openai import OpenAI
from pydantic import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.config import get_settings
from uu_backend.llm.options import reasoning_options_for_model
from uu_backend.models.annotation import LabelCreate
from uu_backend.models.taxonomy import (
    ClassificationCreate,
    DocumentType,
    DocumentTypeCreate,
    DocumentTypeResponse,
    DocumentTypeUpdate,
    FieldAssistantRequest,
    FieldAssistantResponse,
    FieldPropertySuggestion,
    FieldType,
    GlobalFieldCreate,
    GlobalFieldListResponse,
    GlobalFieldUpdate,
)
from uu_backend.repositories import get_repository
from uu_backend.services.classification_service import get_classification_service
from uu_backend.services.extraction_service import get_extraction_service


LABEL_COLORS = [
    "#3b82f6",
    "#ef4444",
    "#f97316",
    "#eab308",
    "#22c55e",
    "#06b6d4",
    "#8b5cf6",
    "#ec4899",
    "#14b8a6",
    "#f59e0b",
]


def _jsonable(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def _validation_error_response(exc: ValidationError) -> Response:
    return Response({"detail": exc.errors()}, status=422)


def _bool_query_param(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _sync_labels_for_schema(repository, doc_type: DocumentType):
    """Synchronize labels to exactly match top-level schema fields for a document type."""
    expected_by_name = {field.name: field for field in (doc_type.schema_fields or [])}

    existing_labels = repository.list_labels(document_type_id=doc_type.id, include_global=False)
    existing_by_name = {label.name: label for label in existing_labels}

    color_idx = 0
    for label_name, field in expected_by_name.items():
        if label_name in existing_by_name:
            continue
        label_data = LabelCreate(
            name=label_name,
            color=LABEL_COLORS[color_idx % len(LABEL_COLORS)],
            description=field.description or f"Schema-derived label for {label_name}",
            document_type_id=doc_type.id,
        )
        try:
            repository.create_label(label_data)
        except Exception:
            pass
        color_idx += 1

    for existing_name, label in existing_by_name.items():
        if existing_name not in expected_by_name:
            repository.delete_label(label.id)


class TaxonomyPrefixView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]
        if not parts:
            return Response({"detail": "Not Found"}, status=404)

        if parts == ["fields"]:
            fields = repository.list_global_fields(search=request.query_params.get("search"))
            payload = GlobalFieldListResponse(fields=fields, total=len(fields))
            return Response(payload.model_dump(mode="json"))

        if len(parts) == 2 and parts[0] == "fields":
            field = repository.get_global_field(parts[1])
            if not field:
                return Response({"detail": "Global field not found"}, status=404)
            return Response(_jsonable(field))

        if parts == ["types"]:
            types = repository.list_document_types()
            return Response({"types": _jsonable(types), "total": len(types)})

        if len(parts) == 2 and parts[0] == "types":
            doc_type = repository.get_document_type(parts[1])
            if not doc_type:
                return Response({"detail": f"Document type {parts[1]} not found"}, status=404)
            return Response(DocumentTypeResponse(type=doc_type).model_dump(mode="json"))

        if len(parts) == 3 and parts[0] == "types" and parts[2] == "schema-versions":
            doc_type = repository.get_document_type(parts[1])
            if not doc_type:
                return Response({"detail": f"Document type {parts[1]} not found"}, status=404)
            versions = repository.list_schema_versions(parts[1])
            return Response({"document_type_id": parts[1], "versions": versions, "total": len(versions)})

        if len(parts) == 3 and parts[0] == "types" and parts[2] == "documents":
            limit_raw = request.query_params.get("limit", "100")
            offset_raw = request.query_params.get("offset", "0")
            try:
                limit = int(limit_raw)
                offset = int(offset_raw)
            except ValueError:
                return Response({"detail": "limit and offset must be integers"}, status=422)
            if limit < 1 or limit > 1000:
                return Response({"detail": "limit must be between 1 and 1000"}, status=422)
            if offset < 0:
                return Response({"detail": "offset must be >= 0"}, status=422)

            doc_type = repository.get_document_type(parts[1])
            if not doc_type:
                return Response({"detail": f"Document type {parts[1]} not found"}, status=404)

            document_ids = repository.get_documents_by_type(parts[1])
            paginated = document_ids[offset : offset + limit]
            return Response(
                {
                    "document_type": doc_type.name,
                    "document_ids": paginated,
                    "total": len(document_ids),
                    "limit": limit,
                    "offset": offset,
                }
            )

        return Response({"detail": "Not Found"}, status=404)

    def post(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]
        body = request.data if isinstance(request.data, dict) else {}

        if parts == ["field-assistant"]:
            try:
                parsed = FieldAssistantRequest.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)

            settings = get_settings()
            if not settings.openai_api_key:
                return Response({"detail": "OPENAI_API_KEY is not configured"}, status=400)

            doc_type = repository.get_document_type(parsed.document_type_id) if parsed.document_type_id else None
            existing_names = parsed.existing_field_names or []
            if doc_type:
                existing_names = sorted({*(f.name for f in (doc_type.schema_fields or [])), *existing_names})

            system_prompt = (
                "You are a document extraction schema assistant.\n"
                "Generate one field suggestion from user intent.\n"
                "Rules:\n"
                "1) Output valid JSON only.\n"
                "2) Field name must be snake_case and not collide with existing_field_names.\n"
                "3) Type must be one of: string, number, date, boolean, object, array.\n"
                "4) extraction_prompt must enforce RAW extraction (no interpretation).\n"
                "5) If type=array and array of objects is appropriate, set items_type=object and include object_properties.\n"
                "6) For non-array fields set items_type=null and object_properties=[].\n"
                "7) Keep output concise and practical for production extraction.\n"
            )
            user_prompt = (
                f"Document type: {doc_type.name if doc_type else 'N/A'}\n"
                f"Document type description: {doc_type.description if doc_type else 'N/A'}\n"
                f"Existing field names: {existing_names}\n"
                f"User intent: {parsed.user_input}\n\n"
                "Return JSON with keys:\n"
                "{\n"
                '  "name": "snake_case_name",\n'
                '  "type": "string|number|date|boolean|object|array",\n'
                '  "description": "short description",\n'
                '  "extraction_prompt": "field extraction prompt",\n'
                '  "items_type": "string|number|date|boolean|object|null",\n'
                '  "object_properties": [{"name":"...","type":"string|number|date|boolean","description":"..."}]\n'
                "}\n"
            )

            model = settings.openai_tagging_model or settings.openai_model
            try:
                response = OpenAI(api_key=settings.openai_api_key).chat.completions.create(
                    model=model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    response_format={"type": "json_object"},
                    **reasoning_options_for_model(model),
                )
                payload = json.loads(response.choices[0].message.content or "{}")
            except Exception as exc:
                return Response({"detail": f"Field assistant failed: {exc}"}, status=500)

            try:
                name = str(payload.get("name", "")).strip().lower().replace(" ", "_")
                if not name:
                    raise ValueError("Missing suggested field name")
                if name in set(existing_names):
                    suffix = 1
                    candidate = f"{name}_{suffix}"
                    while candidate in set(existing_names):
                        suffix += 1
                        candidate = f"{name}_{suffix}"
                    name = candidate

                field_type = FieldType(str(payload.get("type", "string")).strip().lower())
                description = payload.get("description") or None
                extraction_prompt = (
                    str(payload.get("extraction_prompt", "")).strip()
                    or f"Extract the {name.replace('_', ' ')} from the document exactly as shown (RAW)."
                )

                items_raw = payload.get("items_type")
                items_type = None
                if items_raw is not None and str(items_raw).lower() != "null":
                    items_type = FieldType(str(items_raw).strip().lower())

                object_properties = []
                for prop in payload.get("object_properties", []) or []:
                    prop_name = str(prop.get("name", "")).strip().lower().replace(" ", "_")
                    if not prop_name:
                        continue
                    prop_type = FieldType(str(prop.get("type", "string")).strip().lower())
                    object_properties.append(
                        FieldPropertySuggestion(
                            name=prop_name,
                            type=prop_type,
                            description=prop.get("description") or None,
                        )
                    )

                suggestion = FieldAssistantResponse(
                    name=name,
                    type=field_type,
                    description=description,
                    extraction_prompt=extraction_prompt,
                    items_type=items_type,
                    object_properties=object_properties,
                )
                return Response(suggestion.model_dump(mode="json"))
            except Exception as exc:
                return Response({"detail": f"Invalid assistant response: {exc}"}, status=500)

        if parts == ["fields"]:
            try:
                parsed = GlobalFieldCreate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)
            if repository.get_global_field_by_name(parsed.name):
                return Response({"detail": f"Global field '{parsed.name}' already exists"}, status=400)
            try:
                created = repository.create_global_field(parsed)
            except Exception as exc:
                return Response({"detail": f"Failed to create global field: {exc}"}, status=500)
            return Response(_jsonable(created), status=201)

        if parts == ["types"]:
            try:
                parsed = DocumentTypeCreate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)

            existing = repository.get_document_type_by_name(parsed.name)
            if existing:
                return Response({"detail": f"Document type with name '{parsed.name}' already exists"}, status=400)

            try:
                doc_type = repository.create_document_type(parsed)
                _sync_labels_for_schema(repository, doc_type)
                return Response(DocumentTypeResponse(type=doc_type).model_dump(mode="json"), status=201)
            except IntegrityError as exc:
                return Response({"detail": str(exc)}, status=400)
            except Exception as exc:
                return Response({"detail": f"Failed to create document type: {exc}"}, status=500)

        return Response({"detail": "Not Found"}, status=404)

    def put(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]
        body = request.data if isinstance(request.data, dict) else {}

        if len(parts) == 2 and parts[0] == "fields":
            try:
                parsed = GlobalFieldUpdate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)
            if parsed.name:
                existing = repository.get_global_field_by_name(parsed.name)
                if existing and existing.id != parts[1]:
                    return Response({"detail": f"Global field '{parsed.name}' already exists"}, status=400)
            updated = repository.update_global_field(parts[1], parsed)
            if not updated:
                return Response({"detail": "Global field not found"}, status=404)
            return Response(_jsonable(updated))

        if len(parts) == 2 and parts[0] == "types":
            try:
                parsed = DocumentTypeUpdate.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)

            if parsed.name:
                existing = repository.get_document_type_by_name(parsed.name)
                if existing and existing.id != parts[1]:
                    return Response(
                        {"detail": f"Document type with name '{parsed.name}' already exists"},
                        status=400,
                    )

            doc_type = repository.update_document_type(parts[1], parsed)
            if not doc_type:
                return Response({"detail": f"Document type {parts[1]} not found"}, status=404)
            _sync_labels_for_schema(repository, doc_type)
            return Response(DocumentTypeResponse(type=doc_type).model_dump(mode="json"))

        return Response({"detail": "Not Found"}, status=404)

    def delete(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]

        if len(parts) == 2 and parts[0] == "fields":
            deleted = repository.delete_global_field(parts[1])
            if not deleted:
                return Response({"detail": "Global field not found"}, status=404)
            return Response({"status": "success", "message": "Global field deleted"})

        if len(parts) == 2 and parts[0] == "types":
            document_ids = repository.get_documents_by_type(parts[1])
            deleted = repository.delete_document_type(parts[1])
            if not deleted:
                return Response({"detail": f"Document type {parts[1]} not found"}, status=404)
            return Response(
                {
                    "status": "success",
                    "message": "Document type deleted",
                    "documents_unclassified": len(document_ids),
                }
            )

        return Response({"detail": "Not Found"}, status=404)


class ClassifyDocumentView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request, document_id: str):
        repository = get_repository()
        body = request.data if isinstance(request.data, dict) else {}
        try:
            parsed = ClassificationCreate.model_validate(body)
        except ValidationError as exc:
            return _validation_error_response(exc)

        try:
            classification = repository.classify_document(
                document_id=document_id,
                document_type_id=parsed.document_type_id,
                confidence=parsed.confidence,
                labeled_by=parsed.labeled_by,
            )
            return Response({"classification": _jsonable(classification)})
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=404)
        except Exception as exc:
            return Response({"detail": f"Failed to classify document: {exc}"}, status=500)


class AutoClassifyDocumentView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request, document_id: str):
        import traceback
        save = _bool_query_param(request.query_params.get("save"), default=True)
        service = get_classification_service()
        try:
            if save:
                result = async_to_sync(service.classify_document)(document_id, auto_save=True)
            else:
                result = async_to_sync(service.suggest_classification)(document_id)
            return Response(result)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except Exception as exc:
            # Log full traceback for debugging
            tb = traceback.format_exc()
            print(f"Auto-classification error for {document_id}:\n{tb}")
            return Response({"detail": f"Auto-classification failed: {exc}", "traceback": tb}, status=500)


class DocumentClassificationView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, document_id: str):
        repository = get_repository()
        classification = repository.get_classification(document_id)
        if not classification:
            return Response({"detail": f"No classification found for document {document_id}"}, status=404)
        return Response({"classification": _jsonable(classification)})

    def delete(self, request, document_id: str):
        repository = get_repository()
        deleted = repository.delete_classification(document_id)
        if not deleted:
            return Response({"detail": f"No classification found for document {document_id}"}, status=404)
        return Response({"status": "success", "message": "Classification removed"})


class ExtractDocumentView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request, document_id: str):
        use_llm = _bool_query_param(request.query_params.get("use_llm"), default=True)
        use_structured_output = _bool_query_param(request.query_params.get("use_structured_output"), default=False)
        service = get_extraction_service()

        try:
            if use_structured_output:
                result = service.extract_structured(document_id)
            else:
                result = service.extract_from_annotations(document_id, use_llm_refinement=use_llm)

            return Response(
                {
                    "document_id": result.document_id,
                    "document_type_id": result.document_type_id,
                    "fields": [
                        {
                            "field_name": field.field_name,
                            "value": field.value,
                            "confidence": field.confidence,
                            "source_text": field.source_text,
                        }
                        for field in result.fields
                    ],
                    "extracted_at": result.extracted_at.isoformat(),
                }
            )
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except Exception as exc:
            return Response({"detail": f"Extraction failed: {exc}"}, status=500)


class DocumentExtractionView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, document_id: str):
        repository = get_repository()
        result = repository.get_extraction(document_id)
        if not result:
            return Response({"detail": f"No extraction found for document {document_id}"}, status=404)
        return Response(_jsonable(result))

    def delete(self, request, document_id: str):
        repository = get_repository()
        deleted = repository.delete_extraction(document_id)
        if not deleted:
            return Response({"detail": f"No extraction found for document {document_id}"}, status=404)
        return Response({"status": "success", "message": "Extraction deleted"})
