"""Configuration management for Unstructured Unlocked."""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class Settings(BaseModel):
    api_host: str = "0.0.0.0"  # nosec B104
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    debug: bool = False
    file_storage_directory: str = "./data/files"
    retrieval_artifact_directory: str = "./data/retrieval_artifacts"
    qdrant_pdf_storage_directory: str = "./data/qdrant_pdf"
    qdrant_url: str = ""
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    openai_tagging_model: str = ""
    context_model: str = ""
    summary_model: str = ""
    azure_di_endpoint: str = ""
    azure_di_key: str = ""
    openai_reasoning_effort: str = "low"
    # Per-model pricing used to estimate request cost in telemetry.
    # Example:
    # {
    #   "gpt-5-mini": {
    #     "input_per_million": 0.25,
    #     "output_per_million": 2.0,
    #     "cached_input_per_million": 0.025
    #   }
    # }
    openai_model_pricing: dict[str, dict[str, float]] = Field(default_factory=dict)

    @property
    def effective_tagging_model(self) -> str:
        """Return the tagging model, falling back to openai_model if not explicitly set."""
        return self.openai_tagging_model or self.openai_model

    @property
    def effective_context_model(self) -> str:
        """Return the context model, falling back to openai_model if not explicitly set."""
        return self.context_model or self.openai_model

    @property
    def effective_summary_model(self) -> str:
        """Return the summary model, falling back to effective_context_model if not set."""
        return self.summary_model or self.effective_context_model

    @property
    def file_storage_path(self) -> Path:
        """Return the file storage directory as a Path, creating it if necessary."""
        path = Path(self.file_storage_directory)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def retrieval_artifact_path(self) -> Path:
        """Return the retrieval artifact directory as a Path, creating it if necessary."""
        path = Path(self.retrieval_artifact_directory)
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def qdrant_pdf_storage_path(self) -> Path:
        """Return the Qdrant PDF storage directory as a Path, creating it if necessary."""
        path = Path(self.qdrant_pdf_storage_directory)
        path.mkdir(parents=True, exist_ok=True)
        return path


_ENV_TO_FIELD = {
    "API_HOST": "api_host",
    "API_PORT": "api_port",
    "API_PREFIX": "api_prefix",
    "DEBUG": "debug",
    "FILE_STORAGE_DIRECTORY": "file_storage_directory",
    "RETRIEVAL_ARTIFACT_DIRECTORY": "retrieval_artifact_directory",
    "QDRANT_PDF_STORAGE_DIRECTORY": "qdrant_pdf_storage_directory",
    "QDRANT_URL": "qdrant_url",
    "CORS_ORIGINS": "cors_origins",
    "CELERY_BROKER_URL": "celery_broker_url",
    "CELERY_RESULT_BACKEND": "celery_result_backend",
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_MODEL": "openai_model",
    "OPENAI_TAGGING_MODEL": "openai_tagging_model",
    "CONTEXT_MODEL": "context_model",
    "SUMMARY_MODEL": "summary_model",
    "AZURE_DI_ENDPOINT": "azure_di_endpoint",
    "AZURE_DI_KEY": "azure_di_key",
    "OPENAI_REASONING_EFFORT": "openai_reasoning_effort",
    "OPENAI_MODEL_PRICING": "openai_model_pricing",
}


def _coerce_value(field_name: str, raw: str) -> Any:
    if field_name in {
        "api_port",
    }:
        return int(raw)
    if field_name == "debug":
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    if field_name == "cors_origins":
        value = raw.strip()
        if value.startswith("["):
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return [str(item) for item in parsed]
        return [part.strip() for part in value.split(",") if part.strip()]
    if field_name == "openai_model_pricing":
        value = raw.strip()
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("OPENAI_MODEL_PRICING must be a JSON object")
        return parsed
    return raw


def _read_dotenv_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key:
            values[key] = value
    return values


def _read_settings_yaml() -> dict[str, Any]:
    env_path = os.getenv("SETTINGS_FILE")
    candidates = []
    if env_path:
        candidates.append(Path(env_path))
    candidates.append(Path.cwd() / "settings.yml")
    candidates.append(Path(__file__).resolve().parents[2] / "settings.yml")

    for path in candidates:
        if path.exists():
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                raise ValueError(f"settings.yml must contain a mapping, got {type(data)}")
            return data
    return {}


def _build_settings_payload() -> dict[str, Any]:
    payload = Settings().model_dump()
    payload.update(_read_settings_yaml())

    dotenv_values = {}
    for env_path in [Path.cwd() / ".env", Path.cwd().parent / ".env"]:
        if env_path.exists():
            dotenv_values = _read_dotenv_file(env_path)
            break

    for env_key, field_name in _ENV_TO_FIELD.items():
        raw = dotenv_values.get(env_key)
        if raw is not None:
            payload[field_name] = _coerce_value(field_name, raw)

    for env_key, field_name in _ENV_TO_FIELD.items():
        raw = os.getenv(env_key)
        if raw is not None and raw != "":
            payload[field_name] = _coerce_value(field_name, raw)

    return payload


@lru_cache
def get_settings() -> Settings:
    """Return the application settings singleton, built and cached on first call."""
    return Settings(**_build_settings_payload())
