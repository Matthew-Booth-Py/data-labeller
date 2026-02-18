"""Configuration management for Unstructured Unlocked.

Settings precedence (highest to lowest):
1. Runtime environment variables
2. `.env` file (if present)
3. `settings.yml` (if present)
4. In-code defaults
"""

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel


class Settings(BaseModel):
    """Application settings."""

    # API Settings
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    debug: bool = False

    # File Storage Settings
    file_storage_directory: str = "./data/files"

    # CORS Settings
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Celery Settings
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # OpenAI Settings
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    openai_tagging_model: str = "gpt-5-mini"
    openai_reasoning_effort: str = "low"

    # Azure Document Intelligence Settings
    azure_di_endpoint: str = "https://matt-test.cognitiveservices.azure.com/"
    azure_di_key: str = ""

    @property
    def file_storage_path(self) -> Path:
        """Return file storage directory as Path."""
        path = Path(self.file_storage_directory)
        path.mkdir(parents=True, exist_ok=True)
        return path

_ENV_TO_FIELD = {
    "API_HOST": "api_host",
    "API_PORT": "api_port",
    "API_PREFIX": "api_prefix",
    "DEBUG": "debug",
    "FILE_STORAGE_DIRECTORY": "file_storage_directory",
    "CORS_ORIGINS": "cors_origins",
    "CELERY_BROKER_URL": "celery_broker_url",
    "CELERY_RESULT_BACKEND": "celery_result_backend",
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_MODEL": "openai_model",
    "OPENAI_TAGGING_MODEL": "openai_tagging_model",
    "OPENAI_REASONING_EFFORT": "openai_reasoning_effort",
    "AZURE_DI_ENDPOINT": "azure_di_endpoint",
    "AZURE_DI_KEY": "azure_di_key",
}


def _coerce_value(field_name: str, raw: str) -> Any:
    """Coerce env/.env string values into typed settings values."""
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
    return raw


def _read_dotenv_file(path: Path) -> dict[str, str]:
    """Read a simple KEY=VALUE dotenv file."""
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
    """Load settings.yml from cwd or backend root."""
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
    """Merge defaults + settings.yml + .env + runtime environment."""
    payload = Settings().model_dump()

    # settings.yml
    payload.update(_read_settings_yaml())

    # .env - check current directory and parent directory
    dotenv_values = {}
    for env_path in [Path.cwd() / ".env", Path.cwd().parent / ".env"]:
        if env_path.exists():
            dotenv_values = _read_dotenv_file(env_path)
            break
    
    for env_key, field_name in _ENV_TO_FIELD.items():
        raw = dotenv_values.get(env_key)
        if raw is not None:
            payload[field_name] = _coerce_value(field_name, raw)

    # runtime env
    for env_key, field_name in _ENV_TO_FIELD.items():
        raw = os.getenv(env_key)
        if raw is not None and raw != "":
            payload[field_name] = _coerce_value(field_name, raw)

    return payload


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings(**_build_settings_payload())
