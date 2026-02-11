"""Contract fixture sanity checks for /health endpoint."""

import json
from pathlib import Path


def test_health_contract_fixture_shape():
    fixture_path = Path(__file__).with_name("health_contract.json")
    contract = json.loads(fixture_path.read_text(encoding="utf-8"))

    assert contract["endpoint"] == "/health"
    assert contract["method"] == "GET"
    assert contract["required_top_level_keys"] == ["status", "version", "services", "stats"]
    assert contract["required_service_keys"] == ["vector_db", "neo4j", "openai"]
    assert contract["required_stats_keys"] == ["documents", "graph"]
