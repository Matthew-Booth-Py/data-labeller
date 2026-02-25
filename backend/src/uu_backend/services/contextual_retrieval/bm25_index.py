"""BM25 keyword search index for contextual retrieval."""

import os
import pickle  # nosec B403
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from .models import ContextualizedChunk, SearchResult


class BM25Index:
    """
    BM25-based keyword search index.

    Provides lexical/keyword matching to complement semantic vector search.
    Combined with vector search via Reciprocal Rank Fusion.
    """

    def __init__(self, storage_path: str | None = None):
        self.storage_path = storage_path or os.getenv("BM25_INDEX_PATH", "./data/bm25_index.pkl")
        self.index: BM25Okapi | None = None
        self.chunks: list[ContextualizedChunk] = []
        self._loaded = False

    def build(self, chunks: list[ContextualizedChunk]) -> None:
        """
        Build BM25 index from contextualized chunks.

        Args:
            chunks: List of ContextualizedChunk objects to index
        """
        if not chunks:
            return

        tokenized = [self._tokenize(c.contextualized_text) for c in chunks]
        self.index = BM25Okapi(tokenized)
        self.chunks = chunks
        self._loaded = True
        self._save()

    def add(self, chunks: list[ContextualizedChunk]) -> None:
        """
        Add new chunks to the index (rebuilds the full index).

        Note: BM25Okapi doesn't support incremental updates,
        so we rebuild the entire index.

        Args:
            chunks: New chunks to add
        """
        if not self._loaded:
            self._load()

        self.chunks.extend(chunks)

        tokenized = [self._tokenize(c.contextualized_text) for c in self.chunks]
        self.index = BM25Okapi(tokenized)
        self._save()

    def search(
        self,
        query: str,
        top_k: int = 100,
        filter_doc_id: str | None = None,
    ) -> list[SearchResult]:
        """
        Search for chunks matching the query.

        Args:
            query: Search query text
            top_k: Number of results to return
            filter_doc_id: Optional document ID to filter results

        Returns:
            List of SearchResult objects sorted by BM25 score
        """
        if not self._loaded:
            self._load()

        if not self.index or not self.chunks:
            return []

        tokenized_query = self._tokenize(query)
        scores = self.index.get_scores(tokenized_query)

        scored_indices = list(enumerate(scores))

        if filter_doc_id:
            scored_indices = [
                (i, s) for i, s in scored_indices if self.chunks[i].doc_id == filter_doc_id
            ]

        scored_indices.sort(key=lambda x: x[1], reverse=True)
        top_indices = scored_indices[:top_k]

        results = []
        for idx, score in top_indices:
            if score > 0:
                chunk = self.chunks[idx]
                results.append(
                    SearchResult(
                        doc_id=chunk.doc_id,
                        chunk_index=chunk.index,
                        text=chunk.contextualized_text,
                        original_text=chunk.original_text,
                        context=chunk.context,
                        score=float(score),
                        metadata=chunk.metadata,
                    )
                )

        return results

    def delete_document(self, doc_id: str) -> int:
        """
        Delete all chunks for a document and rebuild index.

        Args:
            doc_id: Document ID to delete

        Returns:
            Number of chunks deleted
        """
        if not self._loaded:
            self._load()

        original_count = len(self.chunks)
        self.chunks = [c for c in self.chunks if c.doc_id != doc_id]
        deleted = original_count - len(self.chunks)

        if deleted > 0 and self.chunks:
            tokenized = [self._tokenize(c.contextualized_text) for c in self.chunks]
            self.index = BM25Okapi(tokenized)
            self._save()
        elif deleted > 0:
            self.index = None
            self._save()

        return deleted

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text for BM25.

        Simple whitespace tokenization with lowercasing and
        basic punctuation removal.
        """
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        tokens = text.split()
        return [t for t in tokens if len(t) > 1]

    def _save(self) -> None:
        """Save the index to disk."""
        path = Path(self.storage_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "wb") as f:
            pickle.dump(  # nosec B301
                {
                    "index": self.index,
                    "chunks": self.chunks,
                },
                f,
            )

    def _load(self) -> None:
        """Load the index from disk."""
        path = Path(self.storage_path)

        if path.exists():
            with open(path, "rb") as f:
                data = pickle.load(f)  # nosec B301
                self.index = data.get("index")
                self.chunks = data.get("chunks", [])

        self._loaded = True

    def count(self) -> int:
        """Return total number of chunks in the index."""
        if not self._loaded:
            self._load()
        return len(self.chunks)

    def clear(self) -> None:
        """Clear the index."""
        self.index = None
        self.chunks = []
        self._loaded = True

        path = Path(self.storage_path)
        if path.exists():
            path.unlink()
