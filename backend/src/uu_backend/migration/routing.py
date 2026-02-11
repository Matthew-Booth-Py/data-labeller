"""Route-group resolution utilities for phased Django migration."""

import re
from typing import Optional


_DOCUMENTS_WAVE_B_PATTERNS = (
    re.compile(r"^/api/v1/documents/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/file/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/reprocess/?$"),
)


def resolve_route_group(path: str) -> Optional[str]:
    """Resolve a request path to a migration route group."""
    if path in {"/health", "/api/v1/health"}:
        return "health"
    if path.startswith("/api/v1/timeline"):
        return "timeline"
    if path in {"/api/v1/search", "/api/v1/ask"}:
        return "search"
    if any(pattern.match(path) for pattern in _DOCUMENTS_WAVE_B_PATTERNS):
        return "documents"
    if path.startswith("/api/v1/graph"):
        return "graph"
    if path.startswith("/api/v1/providers"):
        return "providers"
    return None
