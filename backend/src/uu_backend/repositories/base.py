"""Minimal repository protocol used for staged data backend migration."""

from typing import Protocol


class Repository(Protocol):
    """Common repository contract for migration-safe operations."""

    def health(self) -> dict:
        """Return lightweight backend status information."""
