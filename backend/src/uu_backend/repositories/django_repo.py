"""Django ORM-backed repository adapter (phase scaffolding)."""

from uu_backend.database.sqlite_client import get_sqlite_client


class DjangoORMRepository:
    """Repository adapter placeholder for future ORM implementation.

    Phase 3 keeps behavior parity by delegating to SQLite until ORM models
    are fully implemented in phase 4.
    """

    def health(self) -> dict:
        return {
            "backend": "django",
            "status": "sqlite_fallback",
        }

    def __getattr__(self, name: str):
        """Fallback delegation for parity before ORM-backed methods exist."""
        return getattr(get_sqlite_client(), name)
