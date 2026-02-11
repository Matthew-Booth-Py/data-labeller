"""ASGI entrypoint for Django-backed API runtime."""

import os

# Ensure Django loads with local defaults unless explicitly set.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uu_backend.django_project.settings.local")

from uu_backend.django_project.asgi import application as django_app  # noqa: E402

async def application(scope, receive, send):
    """Serve all requests through Django ASGI application."""
    await django_app(scope, receive, send)
