"""Migration route-group resolution tests."""

from uu_backend.migration.routing import resolve_route_group


def test_route_group_resolution_wave_a_paths():
    assert resolve_route_group("/health") == "health"
    assert resolve_route_group("/api/v1/health") == "health"
    assert resolve_route_group("/api/v1/timeline") == "timeline"
    assert resolve_route_group("/api/v1/timeline/range") == "timeline"
    assert resolve_route_group("/api/v1/search") == "search"
    assert resolve_route_group("/api/v1/ask") == "search"


def test_route_group_resolution_wave_b_paths():
    assert resolve_route_group("/api/v1/documents") == "documents"
    assert resolve_route_group("/api/v1/documents/abc/file") == "documents"
    assert resolve_route_group("/api/v1/documents/abc/reprocess") == "documents"
    assert resolve_route_group("/api/v1/graph") == "graph"
    assert resolve_route_group("/api/v1/graph/entities") == "graph"
    assert resolve_route_group("/api/v1/providers/openai") == "providers"


def test_route_group_resolution_non_migrated_path():
    assert resolve_route_group("/api/v1/documents/abc/annotations") is None
    assert resolve_route_group("/api/v1/documents/abc/suggest") is None
    assert resolve_route_group("/api/v1/documents/abc/classify") is None
    assert resolve_route_group("/api/v1/tutorial/next") is None
