"""Document chunking for embedding and retrieval."""

import re
import uuid
from typing import Any

from uu_backend.config import get_settings
from uu_backend.models.document import DocumentChunk


class DocumentChunker:
    """Split documents into chunks for embedding."""

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        """
        Initialize the chunker.

        Args:
            chunk_size: Maximum characters per chunk (default from settings)
            chunk_overlap: Character overlap between chunks (default from settings)
        """
        settings = get_settings()
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def chunk(
        self,
        content: str,
        document_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> list[DocumentChunk]:
        """
        Split content into chunks.

        Args:
            content: The text content to chunk
            document_id: ID of the parent document
            metadata: Additional metadata to include with each chunk

        Returns:
            List of DocumentChunk objects
        """
        if not content or not content.strip():
            return []

        # First, split by paragraphs to preserve semantic boundaries
        paragraphs = self._split_paragraphs(content)

        # Then combine paragraphs into chunks respecting size limits
        chunks = self._create_chunks(paragraphs)

        # Convert to DocumentChunk objects
        base_metadata = metadata or {}
        return [
            DocumentChunk(
                id=str(uuid.uuid4()),
                document_id=document_id,
                content=chunk_text,
                chunk_index=idx,
                metadata={
                    **base_metadata,
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                },
            )
            for idx, chunk_text in enumerate(chunks)
        ]

    def _split_paragraphs(self, content: str) -> list[str]:
        """Split content into paragraphs."""
        # Split on double newlines (paragraph breaks)
        paragraphs = re.split(r"\n\s*\n", content)

        # Clean up each paragraph
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        return paragraphs

    def _create_chunks(self, paragraphs: list[str]) -> list[str]:
        """Combine paragraphs into chunks respecting size limits."""
        chunks: list[str] = []
        current_chunk: list[str] = []
        current_size = 0

        for paragraph in paragraphs:
            paragraph_size = len(paragraph)

            # If single paragraph exceeds chunk size, split it further
            if paragraph_size > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = []
                    current_size = 0

                # Split large paragraph by sentences
                sub_chunks = self._split_large_paragraph(paragraph)
                chunks.extend(sub_chunks)
                continue

            # Check if adding this paragraph exceeds the limit
            new_size = current_size + paragraph_size + (2 if current_chunk else 0)

            if new_size > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append("\n\n".join(current_chunk))

                # Start new chunk with overlap if possible
                overlap_text = self._get_overlap(current_chunk)
                if overlap_text:
                    current_chunk = [overlap_text, paragraph]
                    current_size = len(overlap_text) + len(paragraph) + 2
                else:
                    current_chunk = [paragraph]
                    current_size = paragraph_size
            else:
                current_chunk.append(paragraph)
                current_size = new_size

        # Don't forget the last chunk
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))

        return chunks

    def _split_large_paragraph(self, paragraph: str) -> list[str]:
        """Split a large paragraph into smaller chunks by sentences."""
        # Split by sentence endings
        sentences = re.split(r"(?<=[.!?])\s+", paragraph)

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_size = 0

        for sentence in sentences:
            sentence_size = len(sentence)

            # If single sentence is too long, split by character
            if sentence_size > self.chunk_size:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_size = 0

                # Hard split by character
                for i in range(0, sentence_size, self.chunk_size - self.chunk_overlap):
                    chunk = sentence[i : i + self.chunk_size]
                    chunks.append(chunk)
                continue

            new_size = current_size + sentence_size + (1 if current_chunk else 0)

            if new_size > self.chunk_size and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [sentence]
                current_size = sentence_size
            else:
                current_chunk.append(sentence)
                current_size = new_size

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _get_overlap(self, current_chunk: list[str]) -> str | None:
        """Get overlap text from the end of current chunk."""
        if not current_chunk:
            return None

        # Get last paragraph
        last_paragraph = current_chunk[-1]

        if len(last_paragraph) <= self.chunk_overlap:
            return last_paragraph

        # Take last N characters
        return last_paragraph[-self.chunk_overlap :]


# Module-level instance
_chunker: DocumentChunker | None = None


def get_chunker() -> DocumentChunker:
    """Get or create a DocumentChunker instance."""
    global _chunker
    if _chunker is None:
        _chunker = DocumentChunker()
    return _chunker
