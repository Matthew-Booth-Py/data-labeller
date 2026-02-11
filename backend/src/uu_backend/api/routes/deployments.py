"""Deployment version and endpoint extraction routes."""

from fastapi import APIRouter, File, HTTPException, UploadFile

from uu_backend.database.sqlite_client import get_sqlite_client
from uu_backend.ingestion.converter import get_converter
from uu_backend.models.deployment import (
    DeploymentActivateResponse,
    DeploymentExtractResponse,
    DeploymentVersion,
    DeploymentVersionCreate,
    DeploymentVersionListResponse,
    DeploymentVersionResponse,
)
from uu_backend.models.taxonomy import SchemaField
from uu_backend.services.extraction_service import get_extraction_service

router = APIRouter(prefix="/deployments", tags=["deployments"])


@router.post("/versions", response_model=DeploymentVersionResponse)
def create_deployment_version(request: DeploymentVersionCreate):
    """Create a deployable extraction endpoint version snapshot."""
    sqlite_client = get_sqlite_client()
    try:
        created = sqlite_client.create_deployment_version(
            project_id=request.project_id,
            document_type_id=request.document_type_id,
            prompt_version_id=request.prompt_version_id,
            created_by=request.created_by,
            set_active=request.set_active,
        )
        return DeploymentVersionResponse(version=DeploymentVersion.model_validate(created))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create deployment version: {e}")


@router.get("/projects/{project_id}/versions", response_model=DeploymentVersionListResponse)
def list_deployment_versions(project_id: str):
    """List deployment versions for a project."""
    sqlite_client = get_sqlite_client()
    versions = sqlite_client.list_deployment_versions(project_id)
    return DeploymentVersionListResponse(
        versions=[DeploymentVersion.model_validate(version) for version in versions],
        total=len(versions),
    )


@router.get("/projects/{project_id}/active", response_model=DeploymentVersionResponse)
def get_active_deployment_version(project_id: str):
    """Get the currently active deployment version for a project."""
    sqlite_client = get_sqlite_client()
    active = sqlite_client.get_active_deployment_version(project_id)
    if not active:
        raise HTTPException(status_code=404, detail="No active deployment version found for this project")
    return DeploymentVersionResponse(version=DeploymentVersion.model_validate(active))


@router.post("/projects/{project_id}/versions/{version_id}/activate", response_model=DeploymentActivateResponse)
def activate_deployment_version(project_id: str, version_id: str):
    """Activate a deployment version for a project."""
    sqlite_client = get_sqlite_client()
    activated = sqlite_client.activate_deployment_version(project_id, version_id)
    if not activated:
        raise HTTPException(status_code=404, detail="Deployment version not found for this project")
    return DeploymentActivateResponse(
        status="activated",
        active_version=DeploymentVersion.model_validate(activated),
    )


def _run_deployment_extract(project_id: str, deployment_version: dict, file: UploadFile) -> DeploymentExtractResponse:
    """Run extraction for one deployment version against one uploaded file."""
    converter = get_converter()
    extraction_service = get_extraction_service()

    conversion = converter.convert(file.file, file.filename)
    if not conversion.success:
        raise HTTPException(status_code=400, detail=f"File conversion failed: {conversion.error}")

    schema_fields = [SchemaField.model_validate(field) for field in deployment_version["schema_fields"]]
    extracted_data = extraction_service.extract_structured_from_snapshot(
        content=conversion.content,
        filename=file.filename,
        document_type_name=deployment_version["document_type_name"],
        schema_fields=schema_fields,
        system_prompt=deployment_version.get("system_prompt"),
        model=deployment_version.get("model"),
    )

    return DeploymentExtractResponse(
        project_id=project_id,
        deployment_version_id=deployment_version["id"],
        deployment_version=deployment_version["version"],
        document_type_id=deployment_version["document_type_id"],
        document_type_name=deployment_version["document_type_name"],
        filename=file.filename,
        extracted_data=extracted_data,
    )


@router.post("/projects/{project_id}/extract", response_model=DeploymentExtractResponse)
def extract_with_active_deployment(project_id: str, file: UploadFile = File(...)):
    """Extract using the active deployment endpoint version for a project."""
    sqlite_client = get_sqlite_client()
    active = sqlite_client.get_active_deployment_version(project_id)
    if not active:
        raise HTTPException(status_code=404, detail="No active deployment version found for this project")
    return _run_deployment_extract(project_id, active, file)


@router.post("/projects/{project_id}/versions/{version_id}/extract", response_model=DeploymentExtractResponse)
def extract_with_specific_deployment(project_id: str, version_id: str, file: UploadFile = File(...)):
    """Extract using a specific deployment endpoint version."""
    sqlite_client = get_sqlite_client()
    version = sqlite_client.get_deployment_version(version_id)
    if not version or version["project_id"] != project_id:
        raise HTTPException(status_code=404, detail="Deployment version not found for this project")
    return _run_deployment_extract(project_id, version, file)


@router.post("/projects/{project_id}/v/{version}/extract", response_model=DeploymentExtractResponse)
def extract_with_named_deployment_version(project_id: str, version: str, file: UploadFile = File(...)):
    """
    Extract using a semantic deployment version endpoint.

    Example: /api/v1/deployments/projects/tutorial/v/0.1/extract
    """
    sqlite_client = get_sqlite_client()
    deployment_version = sqlite_client.get_deployment_version_by_name(project_id, version)
    if not deployment_version:
        raise HTTPException(status_code=404, detail="Named deployment version not found for this project")
    return _run_deployment_extract(project_id, deployment_version, file)
