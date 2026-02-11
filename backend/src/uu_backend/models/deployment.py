"""Deployment versioning and extraction endpoint models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DeploymentVersion(BaseModel):
    """Persisted deployable extraction configuration snapshot."""

    id: str
    project_id: str
    version: str
    document_type_id: str
    document_type_name: str
    schema_version_id: Optional[str] = None
    prompt_version_id: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    schema_fields: list[dict[str, Any]] = Field(default_factory=list)
    field_prompt_versions: dict[str, str] = Field(default_factory=dict)
    model: Optional[str] = None
    is_active: bool = False
    created_by: Optional[str] = None
    created_at: datetime


class DeploymentVersionCreate(BaseModel):
    """Request to create a new deployment version snapshot."""

    project_id: str
    document_type_id: str
    prompt_version_id: Optional[str] = None
    created_by: Optional[str] = None
    set_active: bool = True


class DeploymentVersionListResponse(BaseModel):
    """List of deployment versions for a project."""

    versions: list[DeploymentVersion]
    total: int


class DeploymentVersionResponse(BaseModel):
    """Single deployment version response."""

    version: DeploymentVersion


class DeploymentActivateResponse(BaseModel):
    """Response after activating a deployment version."""

    status: str
    active_version: DeploymentVersion


class DeploymentExtractResponse(BaseModel):
    """Extraction result from a deployment endpoint invocation."""

    project_id: str
    deployment_version_id: str
    deployment_version: str
    document_type_id: str
    document_type_name: str
    filename: str
    extracted_data: dict[str, Any]

