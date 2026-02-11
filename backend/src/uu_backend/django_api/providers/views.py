"""DRF views for provider configuration endpoints."""

import os
from datetime import datetime

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from uu_backend.config import get_settings
from uu_backend.repositories import get_repository


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
    repository = get_repository()
    provider = repository.get_llm_provider_settings("openai")
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
    last_tested_at: str | None = None
    connected: bool = False
    model: str = ""


class OpenAIProviderUpdateRequest(BaseModel):
    api_key: str | None = Field(
        default=None,
        description="When omitted, keep existing key. Empty string clears override and falls back to .env.",
    )


class OpenAIProviderTestRequest(BaseModel):
    api_key: str | None = Field(default=None, description="Optional key to test without persisting.")


class OpenAIProviderTestResponse(BaseModel):
    provider: str = "openai"
    connected: bool
    message: str
    masked_api_key: str = ""
    tested_at: str


class OpenAIProviderModel(BaseModel):
    provider: str = "openai"
    model_id: str
    display_name: str | None = None
    is_enabled: bool = True
    created_at: str
    updated_at: str


class OpenAIProviderModelListResponse(BaseModel):
    models: list[OpenAIProviderModel]
    total: int


class OpenAIProviderModelCreateRequest(BaseModel):
    model_id: str = Field(..., min_length=1)
    display_name: str | None = None
    is_enabled: bool = True


class OpenAIProviderModelUpdateRequest(BaseModel):
    display_name: str | None = None
    is_enabled: bool | None = None


class OpenAIProviderModelTestResponse(BaseModel):
    provider: str = "openai"
    model_id: str
    connected: bool
    message: str
    tested_at: str


def _validation_error_response(exc: ValidationError) -> Response:
    return Response({"detail": exc.errors()}, status=422)


class OpenAIProviderStatusView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        repository = get_repository()
        persisted = repository.get_llm_provider_settings("openai") or {}
        key, source = _get_effective_openai_key()
        settings = get_settings()

        last_status = persisted.get("last_test_status", "unknown")
        payload = OpenAIProviderStatusResponse(
            provider="openai",
            masked_api_key=_mask_api_key(key),
            source=source,
            has_key=bool(key),
            last_test_status=last_status,
            last_tested_at=persisted.get("last_tested_at"),
            connected=(last_status == "connected"),
            model=settings.openai_tagging_model or settings.openai_model,
        )
        return Response(payload.model_dump(mode="json"))

    def put(self, request):
        repository = get_repository()
        body = request.data if isinstance(request.data, dict) else {}
        try:
            parsed = OpenAIProviderUpdateRequest.model_validate(body)
        except ValidationError as exc:
            return _validation_error_response(exc)

        if parsed.api_key is not None:
            normalized = parsed.api_key.strip()
            repository.upsert_llm_provider_api_key("openai", normalized or None)
            if normalized:
                os.environ["OPENAI_API_KEY"] = normalized
            else:
                os.environ.pop("OPENAI_API_KEY", None)
            _reset_openai_runtime_singletons()

        return self.get(request)


class OpenAIProviderTestView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request):
        repository = get_repository()
        body = request.data if isinstance(request.data, dict) else {}
        try:
            parsed = OpenAIProviderTestRequest.model_validate(body)
        except ValidationError as exc:
            return _validation_error_response(exc)

        test_key = (parsed.api_key or "").strip()
        if not test_key:
            test_key, _ = _get_effective_openai_key()

        tested_at = datetime.utcnow().isoformat()
        if not test_key:
            repository.update_llm_provider_test_status("openai", "failed")
            return Response({"detail": "No OpenAI API key configured"}, status=400)

        try:
            client = OpenAI(api_key=test_key)
            client.models.list()
            repository.update_llm_provider_test_status("openai", "connected")
            payload = OpenAIProviderTestResponse(
                provider="openai",
                connected=True,
                message="Connection successful",
                masked_api_key=_mask_api_key(test_key),
                tested_at=tested_at,
            )
            return Response(payload.model_dump(mode="json"))
        except Exception as exc:
            repository.update_llm_provider_test_status("openai", "failed")
            return Response({"detail": f"Connection failed: {exc}"}, status=400)


class OpenAIProviderModelListView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def get(self, request):
        enabled_only_raw = str(request.query_params.get("enabled_only", "false")).lower()
        enabled_only = enabled_only_raw in {"1", "true", "yes", "on"}

        repository = get_repository()
        models = repository.list_llm_provider_models("openai", enabled_only=enabled_only)
        payload = OpenAIProviderModelListResponse(
            models=[OpenAIProviderModel.model_validate(model) for model in models],
            total=len(models),
        )
        return Response(payload.model_dump(mode="json"))

    def post(self, request):
        repository = get_repository()
        body = request.data if isinstance(request.data, dict) else {}
        try:
            parsed = OpenAIProviderModelCreateRequest.model_validate(body)
        except ValidationError as exc:
            return _validation_error_response(exc)

        model = repository.upsert_llm_provider_model(
            provider="openai",
            model_id=parsed.model_id.strip(),
            display_name=parsed.display_name,
            is_enabled=parsed.is_enabled,
        )
        payload = OpenAIProviderModel.model_validate(model)
        return Response(payload.model_dump(mode="json"))


class OpenAIProviderModelDetailView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def patch(self, request, model_id: str):
        repository = get_repository()
        body = request.data if isinstance(request.data, dict) else {}
        try:
            parsed = OpenAIProviderModelUpdateRequest.model_validate(body)
        except ValidationError as exc:
            return _validation_error_response(exc)

        updated = repository.update_llm_provider_model(
            provider="openai",
            model_id=model_id,
            display_name=parsed.display_name,
            is_enabled=parsed.is_enabled,
        )
        if not updated:
            return Response({"detail": "Model not found"}, status=404)

        payload = OpenAIProviderModel.model_validate(updated)
        return Response(payload.model_dump(mode="json"))

    def delete(self, request, model_id: str):
        repository = get_repository()
        deleted = repository.delete_llm_provider_model("openai", model_id)
        if not deleted:
            return Response({"detail": "Model not found"}, status=404)
        return Response({"status": "deleted"})


class OpenAIProviderModelTestView(APIView):
    authentication_classes: list = []
    permission_classes: list = []

    def post(self, request, model_id: str):
        repository = get_repository()
        key, _ = _get_effective_openai_key()
        tested_at = datetime.utcnow().isoformat()

        if not key:
            repository.update_llm_provider_test_status("openai", "failed")
            return Response({"detail": "No OpenAI API key configured"}, status=400)

        try:
            client = OpenAI(api_key=key)
            try:
                client.responses.create(
                    model=model_id,
                    input="Reply with OK",
                    max_output_tokens=12,
                )
            except Exception:
                client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": "Reply with OK"}],
                    max_completion_tokens=12,
                )

            repository.update_llm_provider_test_status("openai", "connected")
            payload = OpenAIProviderModelTestResponse(
                provider="openai",
                model_id=model_id,
                connected=True,
                message=f"Model '{model_id}' responded successfully",
                tested_at=tested_at,
            )
            return Response(payload.model_dump(mode="json"))
        except Exception as exc:
            repository.update_llm_provider_test_status("openai", "failed")
            return Response({"detail": f"Model test failed for '{model_id}': {exc}"}, status=400)
