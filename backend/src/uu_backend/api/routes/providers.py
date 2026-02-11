"""LLM provider configuration routes."""

import os
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from openai import OpenAI
from pydantic import BaseModel, Field

from uu_backend.config import get_settings
from uu_backend.database.sqlite_client import get_sqlite_client

router = APIRouter(prefix="/providers", tags=["providers"])


def _mask_api_key(value: str) -> str:
    """Mask an API key for UI display."""
    if not value:
        return ""
    prefix = value[:3].upper().replace("-", "_")
    return f"{prefix}****"


def _reset_openai_runtime_singletons() -> None:
    """Reset cached singletons that hold OpenAI clients/settings."""
    get_settings.cache_clear()

    from uu_backend.llm import openai_client
    from uu_backend.services import (
        classification_service,
        evaluation_service,
        extraction_service,
        label_suggestion_service,
        qa_service,
        schema_based_suggestion_service,
        suggestion_service,
    )

    openai_client._client = None
    classification_service._classification_service = None
    extraction_service._extraction_service = None
    evaluation_service._evaluation_service = None
    suggestion_service._suggestion_service = None
    label_suggestion_service._label_suggestion_service = None
    schema_based_suggestion_service._service = None
    qa_service._qa_service = None


def _get_effective_openai_key() -> tuple[str, str]:
    """Return active key and source."""
    sqlite_client = get_sqlite_client()
    provider = sqlite_client.get_llm_provider_settings("openai")
    override = (provider or {}).get("api_key_override")
    if override:
        return override, "override"
    settings = get_settings()
    if settings.openai_api_key:
        return settings.openai_api_key, "env"
    return "", "none"


class OpenAIProviderStatusResponse(BaseModel):
    provider: str = "openai"
    masked_api_key: str = ""
    source: str = "none"
    has_key: bool = False
    last_test_status: str = "unknown"
    last_tested_at: Optional[str] = None
    connected: bool = False
    model: str = ""


class OpenAIProviderUpdateRequest(BaseModel):
    api_key: Optional[str] = Field(
        default=None,
        description="When omitted, keep existing key. Empty string clears override and falls back to .env.",
    )


class OpenAIProviderTestRequest(BaseModel):
    api_key: Optional[str] = Field(default=None, description="Optional key to test without persisting.")


class OpenAIProviderTestResponse(BaseModel):
    provider: str = "openai"
    connected: bool
    message: str
    masked_api_key: str = ""
    tested_at: str


class OpenAIProviderModel(BaseModel):
    provider: str = "openai"
    model_id: str
    display_name: Optional[str] = None
    is_enabled: bool = True
    created_at: str
    updated_at: str


class OpenAIProviderModelListResponse(BaseModel):
    models: list[OpenAIProviderModel]
    total: int


class OpenAIProviderModelCreateRequest(BaseModel):
    model_id: str = Field(..., min_length=1)
    display_name: Optional[str] = None
    is_enabled: bool = True


class OpenAIProviderModelUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    is_enabled: Optional[bool] = None


@router.get("/openai", response_model=OpenAIProviderStatusResponse)
def get_openai_provider_status():
    """Get OpenAI provider status for settings UI."""
    sqlite_client = get_sqlite_client()
    persisted = sqlite_client.get_llm_provider_settings("openai") or {}
    key, source = _get_effective_openai_key()
    settings = get_settings()

    last_status = persisted.get("last_test_status", "unknown")
    return OpenAIProviderStatusResponse(
        provider="openai",
        masked_api_key=_mask_api_key(key),
        source=source,
        has_key=bool(key),
        last_test_status=last_status,
        last_tested_at=persisted.get("last_tested_at"),
        connected=(last_status == "connected"),
        model=settings.openai_tagging_model or settings.openai_model,
    )


@router.put("/openai", response_model=OpenAIProviderStatusResponse)
def update_openai_provider(request: OpenAIProviderUpdateRequest):
    """Update OpenAI provider API key override."""
    sqlite_client = get_sqlite_client()

    if request.api_key is not None:
        normalized = request.api_key.strip()
        # Empty value clears override and falls back to .env settings.
        sqlite_client.upsert_llm_provider_api_key("openai", normalized or None)
        if normalized:
            os.environ["OPENAI_API_KEY"] = normalized
        else:
            os.environ.pop("OPENAI_API_KEY", None)
        _reset_openai_runtime_singletons()

    return get_openai_provider_status()


@router.post("/openai/test", response_model=OpenAIProviderTestResponse)
def test_openai_provider(request: OpenAIProviderTestRequest):
    """Test OpenAI connectivity with either provided key or effective key."""
    sqlite_client = get_sqlite_client()
    test_key = (request.api_key or "").strip()
    if not test_key:
        test_key, _ = _get_effective_openai_key()

    tested_at = datetime.utcnow().isoformat()
    if not test_key:
        sqlite_client.update_llm_provider_test_status("openai", "failed")
        raise HTTPException(status_code=400, detail="No OpenAI API key configured")

    try:
        client = OpenAI(api_key=test_key)
        # Light connectivity check that verifies authentication and API reachability.
        client.models.list()
        sqlite_client.update_llm_provider_test_status("openai", "connected")
        return OpenAIProviderTestResponse(
            provider="openai",
            connected=True,
            message="Connection successful",
            masked_api_key=_mask_api_key(test_key),
            tested_at=tested_at,
        )
    except Exception as exc:
        sqlite_client.update_llm_provider_test_status("openai", "failed")
        raise HTTPException(status_code=400, detail=f"Connection failed: {exc}") from exc


@router.get("/openai/models", response_model=OpenAIProviderModelListResponse)
def list_openai_models(enabled_only: bool = False):
    """List available OpenAI models for schema configuration."""
    sqlite_client = get_sqlite_client()
    models = sqlite_client.list_llm_provider_models("openai", enabled_only=enabled_only)
    return OpenAIProviderModelListResponse(
        models=[OpenAIProviderModel.model_validate(model) for model in models],
        total=len(models),
    )


@router.post("/openai/models", response_model=OpenAIProviderModel)
def create_or_update_openai_model(request: OpenAIProviderModelCreateRequest):
    """Create or upsert a model in OpenAI provider registry."""
    sqlite_client = get_sqlite_client()
    model = sqlite_client.upsert_llm_provider_model(
        provider="openai",
        model_id=request.model_id.strip(),
        display_name=request.display_name,
        is_enabled=request.is_enabled,
    )
    return OpenAIProviderModel.model_validate(model)


@router.patch("/openai/models/{model_id}", response_model=OpenAIProviderModel)
def update_openai_model(model_id: str, request: OpenAIProviderModelUpdateRequest):
    """Update an existing model entry."""
    sqlite_client = get_sqlite_client()
    updated = sqlite_client.update_llm_provider_model(
        provider="openai",
        model_id=model_id,
        display_name=request.display_name,
        is_enabled=request.is_enabled,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Model not found")
    return OpenAIProviderModel.model_validate(updated)


@router.delete("/openai/models/{model_id}", response_model=dict)
def delete_openai_model(model_id: str):
    """Delete a model from OpenAI provider registry."""
    sqlite_client = get_sqlite_client()
    deleted = sqlite_client.delete_llm_provider_model("openai", model_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"status": "deleted"}
