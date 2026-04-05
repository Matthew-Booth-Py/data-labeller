"""Filesystem-backed storage for PDF retrieval preview artifacts."""

from __future__ import annotations

from pathlib import Path

from uu_backend.config import get_settings


class PDFArtifactStore:
    def __init__(self, base_path: Path | None = None):
        settings = get_settings()
        self.base_path = base_path or settings.retrieval_artifact_path
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save(self, *, document_id: str, artifact_id: str, data: bytes, media_type: str) -> tuple[str, int]:
        extension = self._extension_for_media_type(media_type)
        relative_path = Path(document_id) / f"{artifact_id}{extension}"
        absolute_path = self.base_path / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_bytes(data)
        return relative_path.as_posix(), len(data)

    def read(self, relative_path: str) -> bytes:
        return (self.base_path / relative_path).read_bytes()

    def delete(self, relative_path: str | None) -> None:
        if not relative_path:
            return
        path = self.base_path / relative_path
        path.unlink(missing_ok=True)
        self._cleanup_empty_parents(path.parent)

    def _cleanup_empty_parents(self, path: Path) -> None:
        current = path
        while current != self.base_path and current.exists():
            try:
                current.rmdir()
            except OSError:
                return
            current = current.parent

    def _extension_for_media_type(self, media_type: str) -> str:
        mapping = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "application/json": ".json",
            "text/plain": ".txt",
        }
        return mapping.get(media_type.lower(), ".bin")
