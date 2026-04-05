"""Project models for backend-persisted workspace state."""

from datetime import datetime

from pydantic import BaseModel, Field


class Project(BaseModel):
    id: str
    name: str
    description: str = ""
    type: str = "Document Analysis"
    model: str | None = None
    created_at: datetime
    updated_at: datetime
    document_ids: list[str] = Field(default_factory=list)
    doc_count: int = 0


class ProjectCreate(BaseModel):
    id: str
    name: str
    description: str = ""
    type: str = "Document Analysis"
    model: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    type: str | None = None
    model: str | None = None


class ProjectDocumentMembershipUpdate(BaseModel):
    document_ids: list[str] = Field(default_factory=list)


class ProjectResponse(BaseModel):
    project: Project


class ProjectListResponse(BaseModel):
    projects: list[Project]
    total: int

