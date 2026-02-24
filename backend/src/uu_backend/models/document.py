"""Document-related Pydantic models."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentMetadata(BaseModel):
    """Metadata extracted from a document."""

    filename: str
    file_type: str
    file_size: int | None = None
    date_extracted: datetime | None = None
    page_count: int | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Document(BaseModel):
    """A processed document with its content and metadata."""

    id: str
    filename: str
    file_type: str
    content: str
    date_extracted: datetime | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: DocumentMetadata
    file_path: Optional[str] = None  # Path to original file for vision API
    retrieval_index_status: str = "pending"  # pending, processing, completed, failed
    retrieval_chunks_count: Optional[int] = None
    retrieval_index_progress: Optional[int] = None  # Current chunk being processed
    retrieval_index_total: Optional[int] = None  # Total chunks to process


class DocumentSummary(BaseModel):
    """Summary of a document for listing."""

    id: str
    filename: str
    file_type: str
    date_extracted: datetime | None = None
    created_at: datetime
    token_count: int = 0
    document_type: Optional[Any] = None  # Classification if available (DocumentType)
    retrieval_index_status: str = "pending"  # pending, processing, completed, failed
    retrieval_chunks_count: Optional[int] = None
    retrieval_index_progress: Optional[int] = None  # Current chunk being processed
    retrieval_index_total: Optional[int] = None  # Total chunks to process


class IngestResponse(BaseModel):
    """Response from document ingestion."""

    status: str = "success"
    documents_processed: int
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
