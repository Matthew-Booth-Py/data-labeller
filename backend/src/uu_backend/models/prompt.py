"""Pydantic models for prompt versioning."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PromptVersion(BaseModel):
    """Prompt version for extraction."""
    id: str
    name: str
    document_type_id: Optional[str] = None
    system_prompt: str
    user_prompt_template: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = False
    created_by: Optional[str] = None
    created_at: datetime


class FieldPromptVersion(BaseModel):
    """Field-level prompt version for extraction."""
    id: str
    name: str
    document_type_id: str
    field_name: str
    extraction_prompt: str
    description: Optional[str] = None
    is_active: bool = False
    created_by: Optional[str] = None
    created_at: datetime
