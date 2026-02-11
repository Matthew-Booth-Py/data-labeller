"""Django project package for staged FastAPI-to-Django migration."""

from .celery_app import app as celery_app

__all__ = ("celery_app",)
