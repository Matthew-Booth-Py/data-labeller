"""Route-group resolution utilities for phased Django migration."""

import re
from typing import Optional


_DOCUMENTS_WAVE_B_PATTERNS = (
    re.compile(r"^/api/v1/documents/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/file/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/reprocess/?$"),
)

_SUGGESTIONS_WAVE_C_PATTERNS = (
    re.compile(r"^/api/v1/documents/[^/]+/suggest/?$"),
    re.compile(r"^/api/v1/feedback/?$"),
    re.compile(r"^/api/v1/model/status/?$"),
    re.compile(r"^/api/v1/model/train/?$"),
)

_TUTORIAL_WAVE_C_PATTERNS = (
    re.compile(r"^/api/v1/tutorial/setup/?$"),
    re.compile(r"^/api/v1/tutorial/status/?$"),
    re.compile(r"^/api/v1/tutorial/reset/?$"),
    re.compile(r"^/api/v1/tutorial/sample-documents/?$"),
)

_TAXONOMY_WAVE_D_PATTERNS = (
    re.compile(r"^/api/v1/taxonomy/.+$"),
    re.compile(r"^/api/v1/documents/[^/]+/classify/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/auto-classify/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/classification/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/extract/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/extraction/?$"),
)

_ANNOTATIONS_WAVE_D_PATTERNS = (
    re.compile(r"^/api/v1/labels(?:/.+)?$"),
    re.compile(r"^/api/v1/annotations(?:/.+)?$"),
    re.compile(r"^/api/v1/documents/[^/]+/annotations/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/annotations/stats/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/export/?$"),
    re.compile(r"^/api/v1/documents/[^/]+/suggest-annotations/?$"),
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
    if path in {"/api/v1/ingest", "/api/v1/ingest/status"}:
        return "ingest"
    if any(pattern.match(path) for pattern in _SUGGESTIONS_WAVE_C_PATTERNS):
        return "suggestions"
    if any(pattern.match(path) for pattern in _TUTORIAL_WAVE_C_PATTERNS):
        return "tutorial"
    if any(pattern.match(path) for pattern in _TAXONOMY_WAVE_D_PATTERNS):
        return "taxonomy"
    if any(pattern.match(path) for pattern in _ANNOTATIONS_WAVE_D_PATTERNS):
        return "annotations"
    if path.startswith("/api/v1/deployments"):
        return "deployments"
    if path in {"/api/v1/evaluation", "/api/v1/evaluation/"} or path.startswith("/api/v1/evaluation/"):
        return "evaluation"
    return None
