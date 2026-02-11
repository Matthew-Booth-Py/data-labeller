"""DRF views for annotations and labels endpoints."""

import csv
import io
from datetime import datetime

from pydantic import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.annotation import (
    AnnotationCreate,
    AnnotationStats,
    AnnotationType,
    LabelCreate,
    LabelUpdate,
)
from uu_backend.models.label_suggestion import AcceptSuggestionBody, LabelSuggestionRequest
from uu_backend.repositories import get_repository
from uu_backend.services.label_suggestion_service import get_label_suggestion_service
from uu_backend.services.schema_based_suggestion_service import get_schema_based_suggestion_service


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


def _reconcile_schema_labels(repository, document_type_id: str) -> None:
    """Ensure labels for a document type exactly match current top-level schema fields."""
    doc_type = repository.get_document_type(document_type_id)
    if not doc_type:
        return

    expected_by_name = {field.name: field for field in (doc_type.schema_fields or [])}
    existing = repository.list_labels(document_type_id=document_type_id, include_global=False)
    existing_by_name = {label.name: label for label in existing}

    color_idx = 0
    for label_name, field in expected_by_name.items():
        if label_name in existing_by_name:
            continue
        try:
            repository.create_label(
                LabelCreate(
                    name=label_name,
                    color=LABEL_COLORS[color_idx % len(LABEL_COLORS)],
                    description=field.description or f"Schema-derived label for {label_name}",
                    document_type_id=document_type_id,
                )
            )
        except Exception:
            pass
        color_idx += 1

    for existing_name, label in existing_by_name.items():
        if existing_name not in expected_by_name:
            repository.delete_label(label.id)


class LabelsRootView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        repository = get_repository()
        document_type_id = request.query_params.get("document_type_id")
        include_global = _bool_query_param(request.query_params.get("include_global"), default=True)

        if document_type_id:
            _reconcile_schema_labels(repository, document_type_id)

        labels = repository.list_labels(document_type_id=document_type_id, include_global=include_global)
        return Response({"labels": _jsonable(labels), "total": len(labels)})

    def post(self, request):
        return Response(
            {
                "detail": "Labels are generated from schema fields. Add or update fields in the schema instead.",
            },
            status=409,
        )


class LabelsPrefixView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]
        if len(parts) == 1:
            label = repository.get_label(parts[0])
            if not label:
                return Response({"detail": f"Label {parts[0]} not found"}, status=404)
            return Response(_jsonable(label))
        return Response({"detail": "Not Found"}, status=404)

    def post(self, request, subpath: str):
        parts = [part for part in subpath.strip("/").split("/") if part]
        body = request.data if isinstance(request.data, dict) else {}

        if parts == ["suggest"]:
            try:
                parsed = LabelSuggestionRequest.model_validate(body or {})
            except ValidationError as exc:
                return _validation_error_response(exc)

            service = get_label_suggestion_service()
            try:
                response = service.suggest_labels(parsed)
                return Response(response.model_dump(mode="json"))
            except Exception as exc:
                return Response({"detail": f"Failed to generate label suggestions: {exc}"}, status=500)

        if len(parts) == 3 and parts[0] == "suggestions" and parts[2] == "accept":
            try:
                AcceptSuggestionBody.model_validate(body)
            except ValidationError as exc:
                return _validation_error_response(exc)
            return Response(
                {
                    "detail": "Labels are schema-derived. Add suggested fields to the schema instead of creating standalone labels.",
                },
                status=409,
            )

        if len(parts) == 3 and parts[0] == "suggestions" and parts[2] == "reject":
            return Response({"status": "success", "message": "Suggestion rejected", "id": parts[1]})

        return Response({"detail": "Not Found"}, status=404)

    def put(self, request, subpath: str):
        parts = [part for part in subpath.strip("/").split("/") if part]
        if len(parts) != 1:
            return Response({"detail": "Not Found"}, status=404)

        body = request.data if isinstance(request.data, dict) else {}
        try:
            LabelUpdate.model_validate(body)
        except ValidationError as exc:
            return _validation_error_response(exc)

        return Response(
            {"detail": "Labels are generated from schema fields. Update schema fields instead."},
            status=409,
        )

    def delete(self, request, subpath: str):
        parts = [part for part in subpath.strip("/").split("/") if part]
        if len(parts) != 1:
            return Response({"detail": "Not Found"}, status=404)

        return Response(
            {"detail": "Labels are generated from schema fields. Remove the field from schema instead."},
            status=409,
        )


class AnnotationsRootView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        return Response({"detail": "Not Found"}, status=404)


class AnnotationsPrefixView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, subpath: str):
        repository = get_repository()
        vector_store = get_vector_store()
        parts = [part for part in subpath.strip("/").split("/") if part]

        if parts == ["export"]:
            fmt = request.query_params.get("format", "json")
            label_id = request.query_params.get("label_id")
            all_docs = vector_store.get_all_documents()
            all_annotations: list[dict] = []
            for doc in all_docs:
                annotations = repository.list_annotations(document_id=doc.id, label_id=label_id)
                for ann in annotations:
                    all_annotations.append(
                        {
                            "annotation_id": ann.id,
                            "document_id": ann.document_id,
                            "document_name": doc.filename,
                            "label_id": ann.label_id,
                            "label_name": ann.label_name,
                            "annotation_type": ann.annotation_type,
                            "text": ann.text,
                            "start_offset": ann.start_offset,
                            "end_offset": ann.end_offset,
                            "entity_type": ann.entity_type,
                            "normalized_value": ann.normalized_value,
                            "created_at": ann.created_at,
                            "created_by": ann.created_by,
                        }
                    )

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if fmt.lower() == "csv":
                output = io.StringIO()
                if all_annotations:
                    writer = csv.DictWriter(output, fieldnames=all_annotations[0].keys())
                    writer.writeheader()
                    writer.writerows(all_annotations)
                response = Response(output.getvalue(), content_type="text/csv")
                response["Content-Disposition"] = f"attachment; filename=annotations_export_{timestamp}.csv"
                return response

            payload = {"annotations": all_annotations, "total": len(all_annotations)}
            response = Response(payload, content_type="application/json")
            response["Content-Disposition"] = f"attachment; filename=annotations_export_{timestamp}.json"
            return response

        if len(parts) == 1:
            annotation = repository.get_annotation(parts[0])
            if not annotation:
                return Response({"detail": f"Annotation {parts[0]} not found"}, status=404)
            return Response({"annotation": _jsonable(annotation)})

        return Response({"detail": "Not Found"}, status=404)

    def delete(self, request, subpath: str):
        repository = get_repository()
        parts = [part for part in subpath.strip("/").split("/") if part]
        if len(parts) != 1:
            return Response({"detail": "Not Found"}, status=404)

        deleted = repository.delete_annotation(parts[0])
        if not deleted:
            return Response({"detail": f"Annotation {parts[0]} not found"}, status=404)
        return Response({"status": "success", "message": "Annotation deleted"})


class DocumentAnnotationsView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, document_id: str):
        repository = get_repository()
        annotation_type_raw = request.query_params.get("annotation_type")
        label_id = request.query_params.get("label_id")

        annotation_type = None
        if annotation_type_raw:
            try:
                annotation_type = AnnotationType(annotation_type_raw)
            except ValueError:
                return Response({"detail": f"Invalid annotation_type: {annotation_type_raw}"}, status=422)

        annotations = repository.list_annotations(
            document_id=document_id,
            annotation_type=annotation_type,
            label_id=label_id,
        )
        return Response({"annotations": _jsonable(annotations), "total": len(annotations)})

    def post(self, request, document_id: str):
        repository = get_repository()
        body = request.data if isinstance(request.data, dict) else {}
        try:
            parsed = AnnotationCreate.model_validate(body)
        except ValidationError as exc:
            return _validation_error_response(exc)

        label = repository.get_label(parsed.label_id)
        if not label:
            return Response({"detail": f"Label {parsed.label_id} not found"}, status=404)

        classification = repository.get_classification(document_id)
        if classification:
            doc_type = repository.get_document_type(classification.document_type_id)
            if not doc_type:
                return Response(
                    {
                        "detail": (
                            f"Document type {classification.document_type_id} "
                            "not found for classified document"
                        )
                    },
                    status=400,
                )
            schema_names = {field.name for field in (doc_type.schema_fields or [])}
            if label.document_type_id != doc_type.id or label.name not in schema_names:
                return Response(
                    {
                        "detail": (
                            "Label is not valid for this document type schema. "
                            f"Expected one of: {sorted(schema_names)}"
                        )
                    },
                    status=400,
                )

        if parsed.annotation_type == AnnotationType.TEXT_SPAN:
            if parsed.start_offset is None or parsed.end_offset is None:
                return Response(
                    {"detail": "Text span annotations require start_offset and end_offset"},
                    status=400,
                )
        elif parsed.annotation_type == AnnotationType.BOUNDING_BOX:
            if any(value is None for value in [parsed.x, parsed.y, parsed.width, parsed.height]):
                return Response(
                    {"detail": "Bounding box annotations require x, y, width, height"},
                    status=400,
                )
        elif parsed.annotation_type == AnnotationType.KEY_VALUE:
            if any(value is None for value in [parsed.key_text, parsed.key_start, parsed.value_text, parsed.value_start]):
                return Response(
                    {
                        "detail": (
                            "Key-value annotations require key_text, key_start, "
                            "value_text, value_start"
                        )
                    },
                    status=400,
                )
        elif parsed.annotation_type == AnnotationType.ENTITY:
            if parsed.start_offset is None or parsed.end_offset is None or not parsed.entity_type:
                return Response(
                    {
                        "detail": "Entity annotations require start_offset, end_offset, and entity_type",
                    },
                    status=400,
                )

        try:
            annotation = repository.create_annotation(document_id, parsed)
            return Response({"annotation": _jsonable(annotation)}, status=201)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=404)
        except Exception as exc:
            return Response({"detail": f"Failed to create annotation: {exc}"}, status=500)

    def delete(self, request, document_id: str):
        repository = get_repository()
        count = repository.delete_document_annotations(document_id)
        return Response({"status": "success", "message": f"Deleted {count} annotations", "count": count})


class DocumentAnnotationStatsView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, document_id: str):
        repository = get_repository()
        stats = repository.get_annotation_stats(document_id)
        payload = AnnotationStats(**stats)
        return Response(payload.model_dump(mode="json"))


class DocumentExportView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request, document_id: str):
        repository = get_repository()
        vector_store = get_vector_store()

        fmt = request.query_params.get("format", "json")
        include_content = _bool_query_param(request.query_params.get("include_content"), default=False)

        document = vector_store.get_document(document_id)
        if not document:
            return Response({"detail": f"Document {document_id} not found"}, status=404)

        classification = repository.get_classification(document_id)
        doc_type = repository.get_document_type(classification.document_type_id) if classification else None
        annotations = repository.list_annotations(document_id=document_id)

        export_data = {
            "document": {
                "id": document.id,
                "filename": document.filename,
                "file_type": document.file_type,
                "created_at": str(document.created_at),
                "date_extracted": str(document.date_extracted) if document.date_extracted else None,
            },
            "classification": (
                {
                    "document_type": doc_type.name if doc_type else None,
                    "document_type_id": classification.document_type_id if classification else None,
                    "confidence": classification.confidence if classification else None,
                }
                if classification
                else None
            ),
            "annotations": [
                {
                    "id": ann.id,
                    "label_name": ann.label_name,
                    "label_id": ann.label_id,
                    "type": ann.annotation_type,
                    "text": ann.text,
                    "start_offset": ann.start_offset,
                    "end_offset": ann.end_offset,
                    "entity_type": ann.entity_type,
                    "normalized_value": ann.normalized_value,
                }
                for ann in annotations
            ],
            "extracted_fields": {},
        }

        for ann in annotations:
            label_name = ann.label_name or "unknown"
            if label_name not in export_data["extracted_fields"]:
                export_data["extracted_fields"][label_name] = []
            export_data["extracted_fields"][label_name].append(
                {
                    "text": ann.text,
                    "normalized_value": ann.normalized_value,
                }
            )

        for key, values in export_data["extracted_fields"].items():
            if len(values) == 1:
                export_data["extracted_fields"][key] = values[0]["normalized_value"] or values[0]["text"]

        if include_content:
            export_data["document"]["content"] = document.content

        if fmt.lower() == "csv":
            output = io.StringIO()
            rows = []
            for ann in annotations:
                rows.append(
                    {
                        "document_id": document.id,
                        "document_name": document.filename,
                        "document_type": doc_type.name if doc_type else "",
                        "label_name": ann.label_name,
                        "text": ann.text,
                        "start_offset": ann.start_offset,
                        "end_offset": ann.end_offset,
                        "normalized_value": ann.normalized_value or "",
                    }
                )

            if rows:
                writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            response = Response(output.getvalue(), content_type="text/csv")
            response["Content-Disposition"] = f"attachment; filename={document.filename}_export.csv"
            return response

        response = Response(export_data, content_type="application/json")
        response["Content-Disposition"] = f"attachment; filename={document.filename}_export.json"
        return response


class DocumentSuggestAnnotationsView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request, document_id: str):
        auto_accept = _bool_query_param(request.query_params.get("auto_accept"), default=False)
        service = get_schema_based_suggestion_service()
        try:
            response = service.suggest_annotations(document_id=document_id, auto_accept=auto_accept)
            return Response(_jsonable(response))
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=400)
        except Exception as exc:
            return Response({"detail": f"Suggestion failed: {exc}"}, status=500)
