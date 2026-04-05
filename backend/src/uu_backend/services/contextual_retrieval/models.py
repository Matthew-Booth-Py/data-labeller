"""Data models for Contextual Retrieval."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Chunk:
    """A chunk of text from a document."""

    doc_id: str
    index: int
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextualizedChunk:
    """A chunk with added context for better retrieval."""

    doc_id: str
    index: int
    original_text: str
    context: str
    page_summary: str
    contextualized_text: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def chunk_id(self) -> str:
        """Unique identifier for this chunk."""
        return f"{self.doc_id}_{self.index}"


@dataclass
class SearchResult:
    """A search result with relevance score."""

    doc_id: str
    chunk_index: int
    text: str
    original_text: str
    context: str
    score: float
    metadata: dict[str, Any] = field(default_factory=dict)
    chunk_id: str | None = None
    page_number: int | None = None
    asset_type: str | None = None
    asset_label: str | None = None
    citation_id: str | None = None
    citation_regions: list[dict[str, Any]] = field(default_factory=list)
    preview_artifact_id: str | None = None
