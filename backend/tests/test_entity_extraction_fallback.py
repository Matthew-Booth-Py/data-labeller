"""Tests for rule-based entity extraction fallback."""

from uu_backend.extraction.entities import EntityExtractor
from uu_backend.models.entity import EntityType


class _UnavailableClient:
    def is_available(self) -> bool:
        return False


def test_rule_based_fallback_extracts_entities_when_llm_unavailable():
    extractor = EntityExtractor()
    extractor._client = _UnavailableClient()

    content = """
    ACME Insurance Company issued an invoice to John Smith.
    Service location: Austin, TX.
    """
    result = extractor.extract(content, "doc-1")

    assert len(result.entities) >= 1
    assert any(entity.type == EntityType.ORGANIZATION for entity in result.entities)


def test_rule_based_fallback_creates_title_event_when_no_matches():
    extractor = EntityExtractor()
    extractor._client = _UnavailableClient()

    result = extractor.extract("misc record", "doc-2")

    assert len(result.entities) == 1
    assert result.entities[0].type == EntityType.EVENT
