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


def test_route_group_resolution_wave_c_paths():
    assert resolve_route_group("/api/v1/ingest") == "ingest"
    assert resolve_route_group("/api/v1/ingest/status") == "ingest"
    assert resolve_route_group("/api/v1/documents/abc/suggest") == "suggestions"
    assert resolve_route_group("/api/v1/feedback") == "suggestions"
    assert resolve_route_group("/api/v1/model/status") == "suggestions"
    assert resolve_route_group("/api/v1/model/train") == "suggestions"
    assert resolve_route_group("/api/v1/tutorial/setup") == "tutorial"
    assert resolve_route_group("/api/v1/tutorial/status") == "tutorial"
    assert resolve_route_group("/api/v1/tutorial/reset") == "tutorial"
    assert resolve_route_group("/api/v1/tutorial/sample-documents") == "tutorial"


def test_route_group_resolution_wave_d_paths():
    assert resolve_route_group("/api/v1/taxonomy/types") == "taxonomy"
    assert resolve_route_group("/api/v1/documents/abc/classify") == "taxonomy"
    assert resolve_route_group("/api/v1/documents/abc/auto-classify") == "taxonomy"
    assert resolve_route_group("/api/v1/documents/abc/classification") == "taxonomy"
    assert resolve_route_group("/api/v1/documents/abc/extract") == "taxonomy"
    assert resolve_route_group("/api/v1/documents/abc/extraction") == "taxonomy"
    assert resolve_route_group("/api/v1/labels") == "annotations"
    assert resolve_route_group("/api/v1/annotations/export") == "annotations"
    assert resolve_route_group("/api/v1/documents/abc/annotations") == "annotations"
    assert resolve_route_group("/api/v1/documents/abc/annotations/stats") == "annotations"
    assert resolve_route_group("/api/v1/documents/abc/export") == "annotations"
    assert resolve_route_group("/api/v1/documents/abc/suggest-annotations") == "annotations"
    assert resolve_route_group("/api/v1/deployments/projects/demo/versions") == "deployments"
    assert resolve_route_group("/api/v1/evaluation") == "evaluation"
    assert resolve_route_group("/api/v1/evaluation/prompts") == "evaluation"


def test_route_group_resolution_non_migrated_path():
    assert resolve_route_group("/api/v1/documents/abc/chunks") is None
    assert resolve_route_group("/api/v1/documents/abc/suggest-review") is None
    assert resolve_route_group("/api/v1/tutorial/next") is None
