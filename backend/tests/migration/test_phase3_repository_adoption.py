"""Phase 3 checks for repository abstraction adoption."""

from pathlib import Path

import pytest

from uu_backend.config import get_settings
from uu_backend.repositories.factory import get_repository
from uu_backend.repositories.django_repo import DjangoORMRepository


def test_django_api_has_no_direct_sqlite_client_usage():
    django_api_dir = Path(__file__).resolve().parents[2] / "src" / "uu_backend" / "django_api"
    offenders: list[str] = []
    for py_file in django_api_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if "from uu_backend.database.sqlite_client" in text or "get_sqlite_client(" in text:
            offenders.append(str(py_file))
    assert offenders == []


def test_services_have_no_direct_sqlite_client_usage():
    services_dir = Path(__file__).resolve().parents[2] / "src" / "uu_backend" / "services"
    offenders: list[str] = []
    for py_file in services_dir.rglob("*.py"):
        text = py_file.read_text(encoding="utf-8")
        if "from uu_backend.database.sqlite_client" in text or "get_sqlite_client(" in text:
            offenders.append(str(py_file))
    assert offenders == []


def test_repository_factory_respects_data_backend_env(monkeypatch):
    monkeypatch.setenv("DATA_BACKEND", "django")
    get_settings.cache_clear()
    assert isinstance(get_repository(), DjangoORMRepository)

    monkeypatch.setenv("DATA_BACKEND", "sqlite")
    get_settings.cache_clear()
    with pytest.raises(ValueError):
        get_repository()

    monkeypatch.setenv("DATA_BACKEND", "dual")
    get_settings.cache_clear()
    with pytest.raises(ValueError):
        get_repository()

    get_settings.cache_clear()
