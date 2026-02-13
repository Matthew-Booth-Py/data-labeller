"""DRF views for tutorial setup endpoints."""

import shutil
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.config import get_settings
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.ingestion.chunker import get_chunker
from uu_backend.ingestion.converter import get_converter
from uu_backend.models.annotation import LabelCreate
from uu_backend.models.document import Document, DocumentMetadata
from uu_backend.models.taxonomy import DocumentTypeCreate, FieldType, SchemaField
from uu_backend.repositories import get_repository

SAMPLE_DOCUMENTS = [
    "claim_form_auto_2024.pdf",
    "claim_form_property_2024.pdf",
    "policy_homeowners_2024.pdf",
    "loss_report_theft_2024.pdf",
    "vendor_invoice_repairs_2024.pdf",
    "vendor_invoice_medical_2024.pdf",
]

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
    success: bool
    document_ids: list[str] = Field(default_factory=list)
    document_type_ids: list[str] = Field(default_factory=list)
    label_ids: list[str] = Field(default_factory=list)
    message: str


class TutorialStatusResponse(BaseModel):
    is_setup: bool
    document_count: int
    document_type_count: int
    label_count: int
    sample_document_ids: list[str] = Field(default_factory=list)


def get_sample_docs_path() -> Path:
    docker_path = Path("/app/sample_docs")
    if docker_path.exists():
        return docker_path

    import uu_backend

    package_dir = Path(uu_backend.__file__).parent.parent.parent.parent
    return package_dir / "sample_docs"


class TutorialSetupView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        repository = get_repository()
        document_repo = get_document_repository()
        settings = get_settings()

        document_ids: list[str] = []
        document_type_ids: list[str] = []
        label_ids: list[str] = []

        for type_def in DOCUMENT_TYPES:
            existing = repository.get_document_type_by_name(type_def["name"])
            if existing:
                document_type_ids.append(existing.id)
                continue

            schema_fields = [
                SchemaField(name=field["name"], type=FieldType(field["type"]), description=field["description"])
                for field in type_def["schema_fields"]
            ]
            doc_type = repository.create_document_type(
                DocumentTypeCreate(
                    name=type_def["name"],
                    description=type_def["description"],
                    schema_fields=schema_fields,
                )
            )
            document_type_ids.append(doc_type.id)

        for label_def in DEFAULT_LABELS:
            existing = repository.get_label_by_name(label_def["name"])
            if existing:
                label_ids.append(existing.id)
                continue

            label = repository.create_label(
                LabelCreate(
                    name=label_def["name"],
                    color=label_def["color"],
                    description=label_def["description"],
                )
            )
            label_ids.append(label.id)

        sample_docs_path = get_sample_docs_path()
        if not sample_docs_path.exists():
            payload = TutorialSetupResponse(
                success=False,
                document_ids=document_ids,
                document_type_ids=document_type_ids,
                label_ids=label_ids,
                message=f"Sample documents not found at {sample_docs_path}. Run generate_samples.py first.",
            )
            return Response(payload.model_dump(mode="json"))

        files_dir = Path(settings.file_storage_path)
        files_dir.mkdir(parents=True, exist_ok=True)
        converter = get_converter()
        chunker = get_chunker()

        for filename in SAMPLE_DOCUMENTS:
            src_path = sample_docs_path / filename
            if not src_path.exists():
                continue

            existing_docs = document_repo.get_all_documents()
            existing_doc = next((doc for doc in existing_docs if doc.filename == filename), None)
            if existing_doc:
                document_ids.append(existing_doc.id)
                continue

            doc_id = str(uuid4())
            dest_path = files_dir / f"{doc_id}{src_path.suffix}"
            shutil.copy2(src_path, dest_path)

            try:
                with open(dest_path, "rb") as file_obj:
                    result = converter.convert(file_obj, filename)
                if not result.success:
                    continue

                content = result.content
                doc_chunks = chunker.chunk(content, doc_id)
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
                document_repo.add_document(doc)
                document_ids.append(doc.id)
            except Exception:
                continue

        payload = TutorialSetupResponse(
            success=True,
            document_ids=document_ids,
            document_type_ids=document_type_ids,
            label_ids=label_ids,
            message=(
                f"Tutorial setup complete. Created {len(document_type_ids)} document types, "
                f"{len(label_ids)} labels, and ingested {len(document_ids)} documents."
            ),
        )
        return Response(payload.model_dump(mode="json"))


class TutorialStatusView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        repository = get_repository()
        document_repo = get_document_repository()

        all_docs = document_repo.get_all_documents()
        sample_doc_ids = [doc.id for doc in all_docs if doc.filename in SAMPLE_DOCUMENTS]

        doc_types = repository.list_document_types()
        tutorial_type_count = sum(1 for doc_type in doc_types if any(row["name"] == doc_type.name for row in DOCUMENT_TYPES))

        labels = repository.list_labels()
        tutorial_label_count = sum(1 for label in labels if any(row["name"] == label.name for row in DEFAULT_LABELS))

        payload = TutorialStatusResponse(
            is_setup=len(sample_doc_ids) > 0 and tutorial_type_count > 0,
            document_count=len(sample_doc_ids),
            document_type_count=tutorial_type_count,
            label_count=tutorial_label_count,
            sample_document_ids=sample_doc_ids,
        )
        return Response(payload.model_dump(mode="json"))


class TutorialResetView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        document_repo = get_document_repository()
        settings = get_settings()
        deleted_count = 0

        all_docs = document_repo.get_all_documents()
        for doc in all_docs:
            if doc.filename in SAMPLE_DOCUMENTS:
                document_repo.delete_document(doc.id)
                file_path = Path(settings.file_storage_path) / doc.filename
                if file_path.exists():
                    file_path.unlink()
                deleted_count += 1

        return Response(
            {
                "success": True,
                "deleted_documents": deleted_count,
                "message": f"Tutorial reset complete. Removed {deleted_count} sample documents.",
            }
        )


class TutorialSampleDocumentsView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        document_repo = get_document_repository()
        all_docs = document_repo.get_all_documents()
        sample_docs = []

        for doc in all_docs:
            if doc.filename not in SAMPLE_DOCUMENTS:
                continue

            expected_type = None
            if "claim_form" in doc.filename:
                expected_type = "Insurance Claim Form"
            elif "policy" in doc.filename:
                expected_type = "Policy Document"
            elif "loss_report" in doc.filename:
                expected_type = "Loss Report"
            elif "invoice" in doc.filename:
                expected_type = "Vendor Invoice"

            sample_docs.append(
                {
                    "id": doc.id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "expected_type": expected_type,
                    "is_sample": True,
                }
            )

        return Response(
            {
                "documents": sample_docs,
                "total": len(sample_docs),
                "expected_total": len(SAMPLE_DOCUMENTS),
            }
        )
