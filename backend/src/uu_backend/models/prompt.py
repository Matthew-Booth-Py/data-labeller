"""Pydantic models for prompt versioning."""

from datetime import datetime

from pydantic import BaseModel


class PromptVersion(BaseModel):
    """Prompt version for extraction."""

    id: str
    name: str
    document_type_id: str | None = None
    system_prompt: str
    user_prompt_template: str | None = None
    description: str | None = None
    is_active: bool = False
    created_by: str | None = None
    created_at: datetime


class FieldPromptVersion(BaseModel):
    """Field-level prompt version for extraction."""

    id: str
    name: str
    document_type_id: str
    field_name: str
    extraction_prompt: str
    description: str | None = None
    is_active: bool = False
    created_by: str | None = None
    created_at: datetime
