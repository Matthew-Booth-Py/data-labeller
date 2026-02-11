"""Endpoint inventory sanity checks for migration planning."""

import json
from pathlib import Path


def test_endpoint_inventory_exists_and_has_expected_shape():
    path = Path(__file__).with_name("endpoint_inventory.json")
    assert path.exists(), "endpoint_inventory.json must be generated"

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload.get("groups"), dict)
    assert payload.get("total_endpoints", 0) >= 90


def test_expected_route_groups_present():
    path = Path(__file__).with_name("endpoint_inventory.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    groups = payload["groups"]
    for expected in [
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
    ]:
        assert expected in groups
