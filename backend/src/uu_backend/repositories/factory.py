"""Repository factory driven by DATA_BACKEND setting."""

from uu_backend.config import get_settings

from .django_repo import DjangoORMRepository
from .sqlite_repo import SQLiteRepository


class DualRepository:
    """Dual backend adapter placeholder used during migration validation."""

    def __init__(self):
        self.sqlite = SQLiteRepository()
        self.django = DjangoORMRepository()

    def health(self) -> dict:
        return {
            "backend": "dual",
            "sqlite": self.sqlite.health(),
            "django": self.django.health(),
        }

    def __getattr__(self, name: str):
        """Use SQLite as source of truth while dual validation evolves."""
        return getattr(self.sqlite, name)


def get_repository():
    """Return repository adapter according to DATA_BACKEND setting."""
    backend = get_settings().data_backend.strip().lower()
    if backend == "django":
        return DjangoORMRepository()
    if backend == "dual":
        return DualRepository()
    return SQLiteRepository()
