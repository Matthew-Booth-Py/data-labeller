"""Annotation API routes for document labeling."""

import csv
import io
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.models.annotation import (
    Annotation,
    AnnotationCreate,
    AnnotationListResponse,
    AnnotationResponse,
    AnnotationStats,
    AnnotationType,
    Label,
    LabelCreate,
    LabelListResponse,
    LabelUpdate,
)
from uu_backend.models.label_suggestion import (
    AcceptSuggestionBody,
    AcceptSuggestionRequest,
    LabelSuggestion,
    LabelSuggestionRequest,
    LabelSuggestionResponse,
)
from uu_backend.services.label_suggestion_service import get_label_suggestion_service
from uu_backend.services.schema_based_suggestion_service import get_schema_based_suggestion_service

router = APIRouter()


def _reconcile_schema_labels(client, document_type_id: str) -> None:
    """Ensure labels for a document type exactly match current top-level schema fields."""
    doc_type = client.get_document_type(document_type_id)
    if not doc_type:
        return

    label_colors = [
        '#3b82f6', '#ef4444', '#f97316', '#eab308', '#22c55e',
        '#06b6d4', '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b'
    ]
    expected_by_name = {field.name: field for field in (doc_type.schema_fields or [])}
    existing = client.list_labels(document_type_id=document_type_id, include_global=False)
    existing_by_name = {label.name: label for label in existing}

    color_idx = 0
    for label_name, field in expected_by_name.items():
        if label_name in existing_by_name:
            continue
        try:
            client.create_label(
                LabelCreate(
                    name=label_name,
                    color=label_colors[color_idx % len(label_colors)],
                    description=field.description or f"Schema-derived label for {label_name}",
                    document_type_id=document_type_id,
                )
            )
        except Exception:
            pass
        color_idx += 1

    for existing_name, label in existing_by_name.items():
        if existing_name not in expected_by_name:
            client.delete_label(label.id)


# ============================================================================
# Label Endpoints
# ============================================================================


@router.get("/labels", response_model=LabelListResponse)
async def list_labels(
    document_type_id: Optional[str] = Query(None, description="Filter by document type"),
    include_global: bool = Query(True, description="Include global labels when filtering by type"),
):
    """List all labels, optionally filtered by document type."""
    client = get_sqlite_client()
    if document_type_id:
        _reconcile_schema_labels(client, document_type_id)
    labels = client.list_labels(document_type_id=document_type_id, include_global=include_global)
    return LabelListResponse(labels=labels, total=len(labels))


@router.post("/labels", response_model=Label, status_code=201)
async def create_label(data: LabelCreate):
    """Labels are schema-derived and cannot be created independently."""
    raise HTTPException(
        status_code=409,
        detail="Labels are generated from schema fields. Add or update fields in the schema instead.",
    )


@router.get("/labels/{label_id}", response_model=Label)
async def get_label(label_id: str):
    """Get a label by ID."""
    client = get_sqlite_client()
    label = client.get_label(label_id)

    if not label:
        raise HTTPException(status_code=404, detail=f"Label {label_id} not found")

    return label


@router.put("/labels/{label_id}", response_model=Label)
async def update_label(label_id: str, data: LabelUpdate):
    """Labels are schema-derived and cannot be edited independently."""
    raise HTTPException(
        status_code=409,
        detail="Labels are generated from schema fields. Update schema fields instead.",
    )


@router.delete("/labels/{label_id}")
async def delete_label(label_id: str):
    """Labels are schema-derived and cannot be deleted independently."""
    raise HTTPException(
        status_code=409,
        detail="Labels are generated from schema fields. Remove the field from schema instead.",
    )


# ============================================================================
# Label Suggestion Endpoints
# ============================================================================


@router.post("/labels/suggest", response_model=LabelSuggestionResponse)
async def suggest_labels(request: LabelSuggestionRequest = LabelSuggestionRequest()):
    """Analyze documents and suggest new label types."""
    print(f"📥 Received label suggestion request: {request.model_dump()}")
    service = get_label_suggestion_service()
    
    try:
        response = service.suggest_labels(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate label suggestions: {e}",
        )


@router.post("/labels/suggestions/{suggestion_id}/accept", response_model=Label)
async def accept_label_suggestion(
    suggestion_id: str,
    body: AcceptSuggestionBody,
):
    """Label suggestions can only be applied by adding schema fields."""
    raise HTTPException(
        status_code=409,
        detail="Labels are schema-derived. Add suggested fields to the schema instead of creating standalone labels.",
    )


@router.post("/labels/suggestions/{suggestion_id}/reject")
async def reject_label_suggestion(suggestion_id: str):
    """Reject a label suggestion (for tracking/feedback)."""
    # For now, this is a no-op on the backend
    # Could be extended to store rejection feedback for ML training
    return {"status": "success", "message": "Suggestion rejected", "id": suggestion_id}


# ============================================================================
# Schema-Based Annotation Suggestions
# ============================================================================


@router.post("/documents/{document_id}/suggest-annotations")
async def suggest_annotations_from_schema(
    document_id: str,
    auto_accept: bool = Query(False, description="Automatically create annotations from suggestions")
):
    """
    Suggest annotations for a document based on its schema fields.
    
    Uses OpenAI structured output to:
    1. Extract data according to the document type's schema
    2. Identify text spans where each value was found
    3. Return annotation suggestions with exact character positions
    
    If auto_accept=true, automatically creates the annotations.
    
    Prerequisites:
    - Document must be classified
    - Document type must have schema fields
    - Labels must exist for the schema fields
    """
    service = get_schema_based_suggestion_service()
    
    try:
        response = service.suggest_annotations(
            document_id=document_id,
            auto_accept=auto_accept
        )
        return response
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Suggestion failed: {str(e)}")


# ============================================================================
# Annotation Endpoints
# ============================================================================


@router.get("/documents/{document_id}/annotations", response_model=AnnotationListResponse)
async def list_annotations(
    document_id: str,
    annotation_type: Optional[AnnotationType] = Query(None, description="Filter by type"),
    label_id: Optional[str] = Query(None, description="Filter by label"),
):
    """List annotations for a document."""
    client = get_sqlite_client()
    annotations = client.list_annotations(
        document_id=document_id,
        annotation_type=annotation_type,
        label_id=label_id,
    )
    return AnnotationListResponse(annotations=annotations, total=len(annotations))


@router.post("/documents/{document_id}/annotations", response_model=AnnotationResponse, status_code=201)
async def create_annotation(document_id: str, data: AnnotationCreate):
    """Create a new annotation on a document."""
    client = get_sqlite_client()

    # Enforce schema-derived label scope for classified documents
    label = client.get_label(data.label_id)
    if not label:
        raise HTTPException(status_code=404, detail=f"Label {data.label_id} not found")

    classification = client.get_classification(document_id)
    if classification:
        doc_type = client.get_document_type(classification.document_type_id)
        if not doc_type:
            raise HTTPException(
                status_code=400,
                detail=f"Document type {classification.document_type_id} not found for classified document",
            )
        schema_names = {field.name for field in (doc_type.schema_fields or [])}
        if label.document_type_id != doc_type.id or label.name not in schema_names:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Label is not valid for this document type schema. "
                    f"Expected one of: {sorted(schema_names)}"
                ),
            )

    # Validate based on annotation type
    if data.annotation_type == AnnotationType.TEXT_SPAN:
        if data.start_offset is None or data.end_offset is None:
            raise HTTPException(
                status_code=400,
                detail="Text span annotations require start_offset and end_offset",
            )
    elif data.annotation_type == AnnotationType.BOUNDING_BOX:
        if any(v is None for v in [data.x, data.y, data.width, data.height]):
            raise HTTPException(
                status_code=400,
                detail="Bounding box annotations require x, y, width, height",
            )
    elif data.annotation_type == AnnotationType.KEY_VALUE:
        if any(v is None for v in [data.key_text, data.key_start, data.value_text, data.value_start]):
            raise HTTPException(
                status_code=400,
                detail="Key-value annotations require key_text, key_start, value_text, value_start",
            )
    elif data.annotation_type == AnnotationType.ENTITY:
        if data.start_offset is None or data.end_offset is None or not data.entity_type:
            raise HTTPException(
                status_code=400,
                detail="Entity annotations require start_offset, end_offset, and entity_type",
            )

    try:
        annotation = client.create_annotation(document_id, data)
        return AnnotationResponse(annotation=annotation)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create annotation: {e}")


@router.get("/annotations/{annotation_id}", response_model=AnnotationResponse)
async def get_annotation(annotation_id: str):
    """Get an annotation by ID."""
    client = get_sqlite_client()
    annotation = client.get_annotation(annotation_id)

    if not annotation:
        raise HTTPException(status_code=404, detail=f"Annotation {annotation_id} not found")

    return AnnotationResponse(annotation=annotation)


@router.delete("/annotations/{annotation_id}")
async def delete_annotation(annotation_id: str):
    """Delete an annotation."""
    client = get_sqlite_client()
    deleted = client.delete_annotation(annotation_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Annotation {annotation_id} not found")

    return {"status": "success", "message": "Annotation deleted"}


@router.delete("/documents/{document_id}/annotations")
async def delete_document_annotations(document_id: str):
    """Delete all annotations for a document."""
    client = get_sqlite_client()
    count = client.delete_document_annotations(document_id)

    return {
        "status": "success",
        "message": f"Deleted {count} annotations",
        "count": count,
    }


@router.get("/documents/{document_id}/annotations/stats", response_model=AnnotationStats)
async def get_annotation_stats(document_id: str):
    """Get annotation statistics for a document."""
    client = get_sqlite_client()
    stats = client.get_annotation_stats(document_id)
    return AnnotationStats(**stats)


# ============================================================================
# Export Endpoints
# ============================================================================


@router.get("/annotations/export")
async def export_all_annotations(
    format: str = Query("json", description="Export format: json or csv"),
    label_id: Optional[str] = Query(None, description="Filter by label"),
):
    """Export all annotations as JSON or CSV."""
    client = get_sqlite_client()
    vector_store = get_vector_store()
    
    # Get all documents
    all_docs = vector_store.get_all_documents()
    
    all_annotations = []
    for doc in all_docs:
        annotations = client.list_annotations(document_id=doc.id, label_id=label_id)
        for ann in annotations:
            all_annotations.append({
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
            })
    
    if format.lower() == "csv":
        # Generate CSV
        output = io.StringIO()
        if all_annotations:
            writer = csv.DictWriter(output, fieldnames=all_annotations[0].keys())
            writer.writeheader()
            writer.writerows(all_annotations)
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=annotations_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            },
        )
    else:
        # JSON format
        return StreamingResponse(
            iter([json.dumps({"annotations": all_annotations, "total": len(all_annotations)}, indent=2, default=str)]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename=annotations_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            },
        )


@router.get("/documents/{document_id}/export")
async def export_document(
    document_id: str,
    format: str = Query("json", description="Export format: json or csv"),
    include_content: bool = Query(False, description="Include full document content"),
):
    """Export a document with all its annotations and classification."""
    client = get_sqlite_client()
    vector_store = get_vector_store()
    
    # Get document
    document = vector_store.get_document(document_id)
    if not document:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
    
    # Get classification
    classification = client.get_classification(document_id)
    doc_type = None
    if classification:
        doc_type = client.get_document_type(classification.document_type_id)
    
    # Get annotations
    annotations = client.list_annotations(document_id=document_id)
    
    # Build export data
    export_data = {
        "document": {
            "id": document.id,
            "filename": document.filename,
            "file_type": document.file_type,
            "created_at": str(document.created_at),
            "date_extracted": str(document.date_extracted) if document.date_extracted else None,
        },
        "classification": {
            "document_type": doc_type.name if doc_type else None,
            "document_type_id": classification.document_type_id if classification else None,
            "confidence": classification.confidence if classification else None,
        } if classification else None,
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
        "extracted_fields": {},  # Will be populated from annotations
    }
    
    # Build extracted fields from annotations (group by label)
    for ann in annotations:
        label_name = ann.label_name or "unknown"
        if label_name not in export_data["extracted_fields"]:
            export_data["extracted_fields"][label_name] = []
        export_data["extracted_fields"][label_name].append({
            "text": ann.text,
            "normalized_value": ann.normalized_value,
        })
    
    # Simplify extracted_fields - if only one value, don't use array
    for key, values in export_data["extracted_fields"].items():
        if len(values) == 1:
            export_data["extracted_fields"][key] = values[0]["normalized_value"] or values[0]["text"]
    
    if include_content:
        export_data["document"]["content"] = document.content
    
    if format.lower() == "csv":
        # For CSV, flatten the annotations
        output = io.StringIO()
        rows = []
        for ann in annotations:
            rows.append({
                "document_id": document.id,
                "document_name": document.filename,
                "document_type": doc_type.name if doc_type else "",
                "label_name": ann.label_name,
                "text": ann.text,
                "start_offset": ann.start_offset,
                "end_offset": ann.end_offset,
                "normalized_value": ann.normalized_value or "",
            })
        
        if rows:
            writer = csv.DictWriter(output, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={document.filename}_export.csv"
            },
        )
    else:
        return StreamingResponse(
            iter([json.dumps(export_data, indent=2, default=str)]),
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={document.filename}_export.json"
            },
        )
