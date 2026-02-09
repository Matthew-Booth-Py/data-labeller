"""Document-related Pydantic models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata extracted from a document."""

    filename: str
    file_type: str
    file_size: int | None = None
    date_extracted: datetime | None = None
    page_count: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class DocumentChunk(BaseModel):
    """A chunk of document content for embedding."""

    id: str
    document_id: str
    content: str
    chunk_index: int
    metadata: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """A processed document with its content and metadata."""

    id: str
    filename: str
    file_type: str
    content: str
    date_extracted: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: DocumentMetadata
    chunks: list[DocumentChunk] = Field(default_factory=list)


class DocumentSummary(BaseModel):
    """Summary of a document for listing."""

    id: str
    filename: str
    file_type: str
    date_extracted: datetime | None = None
    created_at: datetime
    chunk_count: int


class IngestResponse(BaseModel):
    """Response from document ingestion."""

    status: str = "success"
    documents_processed: int
    chunks_created: int
    processing_time_seconds: float
    document_ids: list[str]
    errors: list[str] = Field(default_factory=list)


class DocumentResponse(BaseModel):
    """Response containing a single document."""

    document: Document


class DocumentListResponse(BaseModel):
    """Response containing a list of documents."""

    documents: list[DocumentSummary]
    total: int
