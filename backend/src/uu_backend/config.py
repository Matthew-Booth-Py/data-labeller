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

    # ChromaDB Settings
    chroma_persist_directory: str = "./data/chroma"
    chroma_collection_name: str = "documents"

    # File Storage Settings
    file_storage_directory: str = "./data/files"

    # Document Processing Settings
    chunk_size: int = 1000
    chunk_overlap: int = 200

    # CORS Settings
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Neo4j Settings
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"
    neo4j_database: str | None = None

    # OpenAI Settings
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"
    openai_tagging_model: str = "gpt-5-mini"
    openai_reasoning_effort: str = "low"

    # GraphRAG Settings
    graphrag_embedding_model: str = "text-embedding-3-small"
    graphrag_embedding_dimensions: int = 1536
    graphrag_vector_index_name: str = "chunk_embeddings"
    graphrag_similarity_fn: str = "cosine"

    @property
    def chroma_path(self) -> Path:
        """Return ChromaDB persist directory as Path."""
        path = Path(self.chroma_persist_directory)
        path.mkdir(parents=True, exist_ok=True)
        return path

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
    "CHROMA_PERSIST_DIRECTORY": "chroma_persist_directory",
    "CHROMA_COLLECTION_NAME": "chroma_collection_name",
    "FILE_STORAGE_DIRECTORY": "file_storage_directory",
    "CHUNK_SIZE": "chunk_size",
    "CHUNK_OVERLAP": "chunk_overlap",
    "CORS_ORIGINS": "cors_origins",
    "NEO4J_URI": "neo4j_uri",
    "NEO4J_USER": "neo4j_user",
    "NEO4J_PASSWORD": "neo4j_password",
    "NEO4J_DATABASE": "neo4j_database",
    "OPENAI_API_KEY": "openai_api_key",
    "OPENAI_MODEL": "openai_model",
    "OPENAI_TAGGING_MODEL": "openai_tagging_model",
    "OPENAI_REASONING_EFFORT": "openai_reasoning_effort",
    "GRAPHRAG_EMBEDDING_MODEL": "graphrag_embedding_model",
    "GRAPHRAG_EMBEDDING_DIMENSIONS": "graphrag_embedding_dimensions",
    "GRAPHRAG_VECTOR_INDEX_NAME": "graphrag_vector_index_name",
    "GRAPHRAG_SIMILARITY_FN": "graphrag_similarity_fn",
}


def _coerce_value(field_name: str, raw: str) -> Any:
    """Coerce env/.env string values into typed settings values."""
    if field_name in {
        "api_port",
        "chunk_size",
        "chunk_overlap",
        "graphrag_embedding_dimensions",
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

    # .env
    dotenv_values = _read_dotenv_file(Path.cwd() / ".env")
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
