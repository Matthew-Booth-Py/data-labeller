"""Repository factory driven by DATA_BACKEND setting."""

from uu_backend.config import get_settings

from .django_repo import DjangoORMRepository


def get_repository():
    """Return repository adapter according to DATA_BACKEND setting."""
    backend = get_settings().data_backend.strip().lower()
    if backend in {"", "django"}:
        return DjangoORMRepository()
    raise ValueError(
        f"Unsupported DATA_BACKEND='{backend}'. "
        "This runtime is Django/Postgres only; use DATA_BACKEND=django."
    )
