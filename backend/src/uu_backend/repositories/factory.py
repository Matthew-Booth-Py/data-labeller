"""Repository factory for Django ORM repository."""

from .django_repo import DjangoORMRepository


def get_repository():
    """Return Django ORM-backed repository."""
    return DjangoORMRepository()
