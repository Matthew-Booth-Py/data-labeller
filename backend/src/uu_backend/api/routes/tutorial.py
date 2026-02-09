"""Tutorial API routes for the Getting Started wizard."""

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from uu_backend.config import get_settings
from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.database.vector_store import get_vector_store
from uu_backend.ingestion.converter import get_converter
from uu_backend.ingestion.chunker import get_chunker
from uu_backend.models.document import Document
from uu_backend.models.taxonomy import DocumentTypeCreate, SchemaField, FieldType
from uu_backend.models.annotation import LabelCreate

router = APIRouter()


# Sample document definitions
SAMPLE_DOCUMENTS = [
    "claim_form_auto_2024.pdf",
    "claim_form_property_2024.pdf",
    "policy_homeowners_2024.pdf",
    "loss_report_theft_2024.pdf",
    "vendor_invoice_repairs_2024.pdf",
    "vendor_invoice_medical_2024.pdf",
]

# Document type definitions for insurance domain
DOCUMENT_TYPES = [
    {
        "name": "Insurance Claim Form",
        "description": "Forms submitted by policyholders to report a loss and request coverage payment",
        "schema_fields": [
            {"name": "claim_number", "type": "string", "description": "Unique claim identifier (e.g., CLM-2024-AUTO-00147)"},
            {"name": "policy_number", "type": "string", "description": "Associated policy number"},
            {"name": "claimant_name", "type": "string", "description": "Name of the person filing the claim"},
            {"name": "date_of_loss", "type": "date", "description": "When the loss/incident occurred"},
            {"name": "damage_description", "type": "string", "description": "Description of the damage or loss"},
            {"name": "estimated_amount", "type": "number", "description": "Estimated total claim amount"},
        ],
    },
    {
        "name": "Policy Document",
        "description": "Insurance policy declarations and coverage documents",
        "schema_fields": [
            {"name": "policy_number", "type": "string", "description": "Unique policy identifier"},
            {"name": "insured_name", "type": "string", "description": "Name of the primary insured"},
            {"name": "effective_date", "type": "date", "description": "Policy start date"},
            {"name": "expiration_date", "type": "date", "description": "Policy end date"},
            {"name": "coverage_limit", "type": "number", "description": "Primary coverage limit amount"},
            {"name": "premium_amount", "type": "number", "description": "Annual premium amount"},
        ],
    },
    {
        "name": "Loss Report",
        "description": "Detailed reports documenting theft, damage, or other loss events",
        "schema_fields": [
            {"name": "report_number", "type": "string", "description": "Unique loss report identifier"},
            {"name": "incident_date", "type": "date", "description": "Date of the incident"},
            {"name": "police_report", "type": "string", "description": "Police report number if applicable"},
            {"name": "incident_narrative", "type": "string", "description": "Detailed description of the incident"},
            {"name": "total_loss_value", "type": "number", "description": "Total estimated value of the loss"},
        ],
    },
    {
        "name": "Vendor Invoice",
        "description": "Invoices from repair shops, medical providers, and other vendors",
        "schema_fields": [
            {"name": "invoice_number", "type": "string", "description": "Vendor's invoice number"},
            {"name": "vendor_name", "type": "string", "description": "Name of the service provider"},
            {"name": "invoice_date", "type": "date", "description": "Date of the invoice"},
            {"name": "claim_reference", "type": "string", "description": "Associated claim number"},
            {"name": "total_amount", "type": "number", "description": "Total amount due"},
        ],
    },
]

# Default labels for insurance domain
DEFAULT_LABELS = [
    {"name": "Claim Number", "color": "#ef4444", "description": "Unique identifier for insurance claims"},
    {"name": "Policy Number", "color": "#f97316", "description": "Insurance policy identifier"},
    {"name": "Person Name", "color": "#3b82f6", "description": "Names of individuals (claimants, insured, witnesses)"},
    {"name": "Date", "color": "#10b981", "description": "Any significant date (incident, filing, effective)"},
    {"name": "Amount", "color": "#8b5cf6", "description": "Monetary values (damages, premiums, totals)"},
    {"name": "Address", "color": "#06b6d4", "description": "Physical addresses"},
    {"name": "Phone Number", "color": "#84cc16", "description": "Contact phone numbers"},
    {"name": "Description", "color": "#f59e0b", "description": "Descriptive text about incidents or damages"},
]


class TutorialSetupResponse(BaseModel):
    """Response from tutorial setup."""
    
    success: bool
    document_ids: list[str] = Field(default_factory=list)
    document_type_ids: list[str] = Field(default_factory=list)
    label_ids: list[str] = Field(default_factory=list)
    message: str


class TutorialStatusResponse(BaseModel):
    """Status of the tutorial."""
    
    is_setup: bool
    document_count: int
    document_type_count: int
    label_count: int
    sample_document_ids: list[str] = Field(default_factory=list)


def get_sample_docs_path() -> Path:
    """Get the path to sample documents."""
    # In Docker, sample_docs is at /app/sample_docs
    # Locally, it's relative to the backend directory
    docker_path = Path("/app/sample_docs")
    if docker_path.exists():
        return docker_path
    
    # Fallback: look relative to the package
    import uu_backend
    package_dir = Path(uu_backend.__file__).parent.parent.parent.parent
    sample_docs = package_dir / "sample_docs"
    return sample_docs


@router.post("/tutorial/setup", response_model=TutorialSetupResponse)
async def setup_tutorial():
    """
    Initialize the tutorial with sample documents and data.
    
    This endpoint:
    1. Creates document types for the insurance domain
    2. Copies and ingests sample PDF documents
    3. Creates default labels for annotation
    
    If the tutorial is already set up, this will skip existing items.
    """
    sqlite_client = get_sqlite_client()
    vector_store = get_vector_store()
    settings = get_settings()
    
    document_ids = []
    document_type_ids = []
    label_ids = []
    
    # 1. Create document types
    for type_def in DOCUMENT_TYPES:
        existing = sqlite_client.get_document_type_by_name(type_def["name"])
        if existing:
            document_type_ids.append(existing.id)
            continue
        
        schema_fields = [
            SchemaField(
                name=f["name"],
                type=FieldType(f["type"]),
                description=f["description"],
            )
            for f in type_def["schema_fields"]
        ]
        
        doc_type = sqlite_client.create_document_type(
            DocumentTypeCreate(
                name=type_def["name"],
                description=type_def["description"],
                schema_fields=schema_fields,
            )
        )
        document_type_ids.append(doc_type.id)
    
    # 2. Create default labels
    for label_def in DEFAULT_LABELS:
        existing = sqlite_client.get_label_by_name(label_def["name"])
        if existing:
            label_ids.append(existing.id)
            continue
        
        label = sqlite_client.create_label(
            LabelCreate(
                name=label_def["name"],
                color=label_def["color"],
                description=label_def["description"],
            )
        )
        label_ids.append(label.id)
    
    # 3. Copy and ingest sample documents
    sample_docs_path = get_sample_docs_path()
    
    if not sample_docs_path.exists():
        return TutorialSetupResponse(
            success=False,
            document_ids=document_ids,
            document_type_ids=document_type_ids,
            label_ids=label_ids,
            message=f"Sample documents not found at {sample_docs_path}. Run generate_samples.py first.",
        )
    
    files_dir = Path(settings.file_storage_path)
    files_dir.mkdir(parents=True, exist_ok=True)
    
    for filename in SAMPLE_DOCUMENTS:
        src_path = sample_docs_path / filename
        
        if not src_path.exists():
            continue
        
        # Check if already ingested by filename
        existing_docs = vector_store.get_all_documents()
        already_exists = any(d.filename == filename for d in existing_docs)
        
        if already_exists:
            # Find the existing document ID
            for d in existing_docs:
                if d.filename == filename:
                    document_ids.append(d.id)
                    break
            continue
        
        # Create document ID first (before copying)
        from uuid import uuid4
        doc_id = str(uuid4())
        
        # Copy file to storage with document ID as name
        file_ext = src_path.suffix
        dest_path = files_dir / f"{doc_id}{file_ext}"
        shutil.copy2(src_path, dest_path)
        
        try:
            # Convert document
            converter = get_converter()
            with open(dest_path, "rb") as f:
                result = converter.convert(f, filename)
            
            if not result.success:
                print(f"Failed to convert {filename}: {result.error}")
                continue
            
            content = result.content
            
            # Import datetime and DocumentMetadata
            from datetime import datetime
            from uu_backend.models.document import DocumentMetadata
            
            # Chunk document using chunker
            chunker = get_chunker()
            doc_chunks = chunker.chunk(content, doc_id)
            
            # Create document
            doc = Document(
                id=doc_id,
                filename=filename,
                file_type=dest_path.suffix.lstrip("."),
                content=content,
                chunks=doc_chunks,
                metadata=DocumentMetadata(
                    filename=filename,
                    file_type=dest_path.suffix.lstrip("."),
                    page_count=result.metadata.page_count,
                    extra={
                        "word_count": len(content.split()) if content else 0,
                        "source": "tutorial",
                        "file_path": str(dest_path),
                    },
                ),
                created_at=datetime.utcnow(),
            )
            
            # Store in vector store
            vector_store.add_document(doc)
            document_ids.append(doc.id)
            
        except Exception as e:
            print(f"Error ingesting {filename}: {e}")
            continue
    
    return TutorialSetupResponse(
        success=True,
        document_ids=document_ids,
        document_type_ids=document_type_ids,
        label_ids=label_ids,
        message=f"Tutorial setup complete. Created {len(document_type_ids)} document types, {len(label_ids)} labels, and ingested {len(document_ids)} documents.",
    )


@router.get("/tutorial/status", response_model=TutorialStatusResponse)
async def get_tutorial_status():
    """
    Check if the tutorial has been set up.
    
    Returns information about the current tutorial state including
    counts of documents, types, and labels.
    """
    sqlite_client = get_sqlite_client()
    vector_store = get_vector_store()
    
    # Check for sample documents
    all_docs = vector_store.get_all_documents()
    sample_doc_ids = []
    for doc in all_docs:
        if doc.filename in SAMPLE_DOCUMENTS:
            sample_doc_ids.append(doc.id)
    
    # Count document types
    doc_types = sqlite_client.list_document_types()
    tutorial_type_count = sum(
        1 for dt in doc_types 
        if any(t["name"] == dt.name for t in DOCUMENT_TYPES)
    )
    
    # Count labels
    labels = sqlite_client.list_labels()
    tutorial_label_count = sum(
        1 for l in labels 
        if any(lb["name"] == l.name for lb in DEFAULT_LABELS)
    )
    
    is_setup = len(sample_doc_ids) > 0 and tutorial_type_count > 0
    
    return TutorialStatusResponse(
        is_setup=is_setup,
        document_count=len(sample_doc_ids),
        document_type_count=tutorial_type_count,
        label_count=tutorial_label_count,
        sample_document_ids=sample_doc_ids,
    )


@router.post("/tutorial/reset")
async def reset_tutorial():
    """
    Reset the tutorial by removing sample documents.
    
    Note: This only removes sample documents, not document types or labels
    which may be used by other documents.
    """
    vector_store = get_vector_store()
    settings = get_settings()
    
    deleted_count = 0
    
    # Find and delete sample documents
    all_docs = vector_store.get_all_documents()
    for doc in all_docs:
        if doc.filename in SAMPLE_DOCUMENTS:
            # Delete from vector store
            vector_store.delete_document(doc.id)
            
            # Delete file
            file_path = Path(settings.file_storage_path) / doc.filename
            if file_path.exists():
                file_path.unlink()
            
            deleted_count += 1
    
    return {
        "success": True,
        "deleted_documents": deleted_count,
        "message": f"Tutorial reset complete. Removed {deleted_count} sample documents.",
    }


@router.get("/tutorial/sample-documents")
async def list_sample_documents():
    """
    List the sample documents available for the tutorial.
    
    Returns information about each sample document including
    its type and key characteristics.
    """
    vector_store = get_vector_store()
    
    # Find sample documents
    all_docs = vector_store.get_all_documents()
    sample_docs = []
    
    for doc in all_docs:
        if doc.filename in SAMPLE_DOCUMENTS:
            # Determine expected type
            expected_type = None
            if "claim_form" in doc.filename:
                expected_type = "Insurance Claim Form"
            elif "policy" in doc.filename:
                expected_type = "Policy Document"
            elif "loss_report" in doc.filename:
                expected_type = "Loss Report"
            elif "invoice" in doc.filename:
                expected_type = "Vendor Invoice"
            
            sample_docs.append({
                "id": doc.id,
                "filename": doc.filename,
                "file_type": doc.file_type,
                "expected_type": expected_type,
                "is_sample": True,
            })
    
    return {
        "documents": sample_docs,
        "total": len(sample_docs),
        "expected_total": len(SAMPLE_DOCUMENTS),
    }
