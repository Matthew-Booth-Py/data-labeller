"""Composite ASGI app that dispatches between FastAPI and Django by route group."""

import os
from typing import Optional

from uu_backend.config import get_settings
from uu_backend.migration.routing import resolve_route_group

# Ensure Django loads with local defaults unless explicitly set.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uu_backend.django_project.settings.local")

from uu_backend.api.main import app as fastapi_app  # noqa: E402
from uu_backend.django_project.asgi import application as django_app  # noqa: E402

ALL_ROUTE_GROUPS = {
    "health",
    "timeline",
    "search",
    "documents",
    "graph",
    "providers",
    "ingest",
    "suggestions",
    "tutorial",
    "taxonomy",
    "annotations",
    "deployments",
    "evaluation",
}


def _route_group(path: str) -> Optional[str]:
    """Backward-compatible alias for route-group resolution."""
    return resolve_route_group(path)


async def application(scope, receive, send):
    """Dispatch to Django for migrated groups, otherwise FastAPI."""
    if scope.get("type") != "http":
        await django_app(scope, receive, send)
        return

    path = scope.get("path", "")
    settings = get_settings()
    fallback_enabled = settings.dispatcher_enable_fastapi_fallback
    group = resolve_route_group(path)
    migrated_groups = settings.django_migrated_groups_set

    if not fallback_enabled:
        # Phase 5 default: Django owns all known API groups and docs/health endpoints.
        if group in ALL_ROUTE_GROUPS:
            await django_app(scope, receive, send)
            return
        if path in {"/health", "/docs", "/redoc"} or path.startswith("/api/"):
            await django_app(scope, receive, send)
            return
        await django_app(scope, receive, send)
        return

    # Rollback mode: preserve phased routing behavior.
    if group and group in migrated_groups:
        await django_app(scope, receive, send)
        return

    await fastapi_app(scope, receive, send)
