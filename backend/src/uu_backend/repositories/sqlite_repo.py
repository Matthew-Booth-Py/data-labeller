"""SQLite-backed repository adapter."""

from uu_backend.database.sqlite_client import get_sqlite_client


class SQLiteRepository:
    """Repository adapter for existing SQLite client."""

    def health(self) -> dict:
        client = get_sqlite_client()
        return {
            "backend": "sqlite",
            "path": str(client.db_path),
        }

    def __getattr__(self, name: str):
        """Delegate unknown operations to the existing SQLite client."""
        return getattr(get_sqlite_client(), name)
