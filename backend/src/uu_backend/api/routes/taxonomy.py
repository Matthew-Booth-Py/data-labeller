"""Taxonomy API routes for document type management."""

from fastapi import APIRouter, HTTPException, Query
from sqlite3 import IntegrityError
from uuid import uuid4

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.services.classification_service import get_classification_service
from uu_backend.services.extraction_service import get_extraction_service
from uu_backend.models.taxonomy import (
    Classification,
    ClassificationCreate,
    ClassificationResponse,
    DocumentType,
    DocumentTypeCreate,
    DocumentTypeListResponse,
    DocumentTypeResponse,
    DocumentTypeUpdate,
)
from uu_backend.models.annotation import LabelCreate

router = APIRouter()


# Helper function to auto-create labels for nested object properties
def _auto_create_labels_for_schema(client, doc_type: DocumentType):
    """Automatically create labels for nested object properties in schema fields."""
    label_colors = [
        '#3b82f6', '#ef4444', '#f97316', '#eab308', '#22c55e',
        '#06b6d4', '#8b5cf6', '#ec4899', '#14b8a6', '#f59e0b'
    ]
    color_idx = 0
    
    for field in doc_type.schema_fields:
        # Check if this is an array of objects
        if field.type.value == "array" and field.items and field.items.type.value == "object":
            if field.items.properties:
                # Create labels for each property
                for prop_name, prop_schema in field.items.properties.items():
                    # Create label name as field_name + property_name
                    label_name = f"{field.name}_{prop_name}"
                    
                    # Check if label already exists
                    existing_labels = client.list_labels()
                    label_exists = any(label.name == label_name for label in existing_labels)
                    
                    if not label_exists:
                        # Create the label
                        label_data = LabelCreate(
                            name=label_name,
                            color=label_colors[color_idx % len(label_colors)],
                            description=prop_schema.description or f"{prop_name} from {field.name}",
                            document_type_id=doc_type.id
                        )
                        try:
                            created_label = client.create_label(label_data)
                            print(f"✓ Auto-created label: {label_name} (ID: {created_label.id}) for document type {doc_type.name}")
                            color_idx += 1
                        except Exception as e:
                            import traceback
                            print(f"❌ Error creating label {label_name}: {e}")
                            print(traceback.format_exc())


# Document Type Endpoints


@router.get("/taxonomy/types", response_model=DocumentTypeListResponse)
async def list_document_types():
    """List all document types."""
    client = get_sqlite_client()
    types = client.list_document_types()
    return DocumentTypeListResponse(types=types, total=len(types))


@router.post("/taxonomy/types", response_model=DocumentTypeResponse, status_code=201)
async def create_document_type(data: DocumentTypeCreate):
    """Create a new document type."""
    client = get_sqlite_client()

    # Check if name already exists
    existing = client.get_document_type_by_name(data.name)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"Document type with name '{data.name}' already exists",
        )

    try:
        doc_type = client.create_document_type(data)
        
        # Auto-create labels for nested object properties
        _auto_create_labels_for_schema(client, doc_type)
        
        return DocumentTypeResponse(type=doc_type)
    except IntegrityError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create document type: {e}")


@router.get("/taxonomy/types/{type_id}", response_model=DocumentTypeResponse)
async def get_document_type(type_id: str):
    """Get a document type by ID."""
    client = get_sqlite_client()
    doc_type = client.get_document_type(type_id)

    if not doc_type:
        raise HTTPException(status_code=404, detail=f"Document type {type_id} not found")

    return DocumentTypeResponse(type=doc_type)


@router.put("/taxonomy/types/{type_id}", response_model=DocumentTypeResponse)
async def update_document_type(type_id: str, data: DocumentTypeUpdate):
    """Update a document type."""
    client = get_sqlite_client()

    # Check if new name conflicts with existing
    if data.name:
        existing = client.get_document_type_by_name(data.name)
        if existing and existing.id != type_id:
            raise HTTPException(
                status_code=400,
                detail=f"Document type with name '{data.name}' already exists",
            )

    doc_type = client.update_document_type(type_id, data)
    
    # Auto-create labels for any new nested object properties
    if data.schema_fields:
        _auto_create_labels_for_schema(client, doc_type)

    if not doc_type:
        raise HTTPException(status_code=404, detail=f"Document type {type_id} not found")

    return DocumentTypeResponse(type=doc_type)


@router.delete("/taxonomy/types/{type_id}")
async def delete_document_type(type_id: str):
    """Delete a document type."""
    client = get_sqlite_client()

    # Get count of documents using this type
    document_ids = client.get_documents_by_type(type_id)
    
    deleted = client.delete_document_type(type_id)

    if not deleted:
        raise HTTPException(status_code=404, detail=f"Document type {type_id} not found")

    return {
        "status": "success",
        "message": f"Document type deleted",
        "documents_unclassified": len(document_ids),
    }


# Document Classification Endpoints


@router.post("/documents/{document_id}/classify", response_model=ClassificationResponse)
async def classify_document(document_id: str, data: ClassificationCreate):
    """Classify a document with a document type."""
    client = get_sqlite_client()

    try:
        classification = client.classify_document(
            document_id=document_id,
            document_type_id=data.document_type_id,
            confidence=data.confidence,
            labeled_by=data.labeled_by,
        )
        return ClassificationResponse(classification=classification)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to classify document: {e}")


@router.post("/documents/{document_id}/auto-classify")
async def auto_classify_document(
    document_id: str,
    save: bool = Query(True, description="Whether to save the classification"),
):
    """
    Automatically classify a document using LLM.
    
    This endpoint uses an LLM to analyze the document content
    and determine the most appropriate document type.
    
    Args:
        document_id: The document to classify
        save: If True, saves the classification. If False, only suggests.
    
    Returns:
        Classification result with confidence and reasoning.
    """
    service = get_classification_service()
    
    try:
        if save:
            result = await service.classify_document(document_id, auto_save=True)
        else:
            result = await service.suggest_classification(document_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Auto-classification failed: {e}")


@router.get("/documents/{document_id}/classification", response_model=ClassificationResponse)
async def get_document_classification(document_id: str):
    """Get the classification for a document."""
    client = get_sqlite_client()
    classification = client.get_classification(document_id)

    if not classification:
        raise HTTPException(
            status_code=404,
            detail=f"No classification found for document {document_id}",
        )

    return ClassificationResponse(classification=classification)


@router.delete("/documents/{document_id}/classification")
async def delete_document_classification(document_id: str):
    """Remove classification from a document."""
    client = get_sqlite_client()
    deleted = client.delete_classification(document_id)

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No classification found for document {document_id}",
        )

    return {"status": "success", "message": "Classification removed"}


@router.get("/taxonomy/types/{type_id}/documents")
async def get_documents_by_type(
    type_id: str,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Get all documents classified with a specific type."""
    client = get_sqlite_client()

    # Verify type exists
    doc_type = client.get_document_type(type_id)
    if not doc_type:
        raise HTTPException(status_code=404, detail=f"Document type {type_id} not found")

    document_ids = client.get_documents_by_type(type_id)

    # Apply pagination
    paginated = document_ids[offset : offset + limit]

    return {
        "document_type": doc_type.name,
        "document_ids": paginated,
        "total": len(document_ids),
        "limit": limit,
        "offset": offset,
    }


# Document Extraction Endpoints


@router.post("/documents/{document_id}/extract")
async def extract_document(
    document_id: str,
    use_llm: bool = Query(True, description="Use LLM to refine extraction"),
):
    """
    Extract structured data from a document.
    
    Uses the document's annotations and maps them to the schema fields
    defined for its document type. Optionally uses LLM to refine values.
    
    Prerequisites:
    - Document must be classified with a document type
    - Document type must have schema fields defined
    - Document should have annotations for best results
    """
    service = get_extraction_service()
    
    try:
        result = service.extract_from_annotations(document_id, use_llm_refinement=use_llm)
        return {
            "document_id": result.document_id,
            "document_type_id": result.document_type_id,
            "fields": [
                {
                    "field_name": f.field_name,
                    "value": f.value,
                    "confidence": f.confidence,
                    "source_text": f.source_text,
                }
                for f in result.fields
            ],
            "extracted_at": result.extracted_at.isoformat(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Extraction failed: {e}")


@router.get("/documents/{document_id}/extraction")
async def get_document_extraction(document_id: str):
    """Get the saved extraction result for a document."""
    client = get_sqlite_client()
    result = client.get_extraction(document_id)
    
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No extraction found for document {document_id}",
        )
    
    return result


@router.delete("/documents/{document_id}/extraction")
async def delete_document_extraction(document_id: str):
    """Delete the extraction for a document."""
    client = get_sqlite_client()
    deleted = client.delete_extraction(document_id)
    
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"No extraction found for document {document_id}",
        )
    
    return {"status": "success", "message": "Extraction deleted"}
