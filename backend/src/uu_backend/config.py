"""Configuration management for Unstructured Unlocked."""

from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

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

    # SQLite Settings
    sqlite_database_path: str = "./data/taxonomy.db"

    # Document Processing Settings
    chunk_size: int = 1000  # characters per chunk
    chunk_overlap: int = 200  # overlap between chunks

    # CORS Settings
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Neo4j Settings
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # OpenAI Settings
    openai_api_key: str = ""
    openai_model: str = "gpt-5-mini"

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


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
