"""Tests for QA service Text2Cypher behavior."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest
from neo4j_graphrag.exceptions import Text2CypherRetrievalError

from uu_backend.config import get_settings
from uu_backend.services.qa_service import QAService


class _FakeGraphRAG:
    def __init__(self):
        self.calls: list[dict] = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            answer="stub-answer",
            retriever_result=SimpleNamespace(items=[]),
        )


def test_ask_with_graphrag_uses_n_context_as_top_k(monkeypatch):
    service = QAService()
    fake_rag = _FakeGraphRAG()
    monkeypatch.setattr(service, "_get_graphrag", lambda: fake_rag)

    result = service._ask_with_graphrag(
        question="What entities exist?",
        document_ids=None,
        n_context=7,
    )

    assert result["answer"] == "stub-answer"
    assert fake_rag.calls == [
        {
            "query_text": "What entities exist?",
            "retriever_config": {"top_k": 7},
            "return_context": True,
            "response_fallback": service.NO_EVIDENCE_ANSWER,
        }
    ]


def test_ask_with_graphrag_uses_document_scope_when_document_ids_present(monkeypatch):
    service = QAService()
    captured: dict = {}

    def _fake_scope(**kwargs):
        captured.update(kwargs)
        return {
            "answer": "scoped-answer",
            "confidence": 1.0,
            "sources": [],
            "referenced_sources": [],
        }

    monkeypatch.setattr(service, "_ask_with_document_scope", _fake_scope)

    result = service._ask_with_graphrag(
        question="Find entities",
        document_ids=["doc-1", "", "doc-2"],
        n_context=5,
    )

    assert result["answer"] == "scoped-answer"
    assert captured == {
        "question": "Find entities",
        "document_ids": ["doc-1", "doc-2"],
        "n_context": 5,
    }


def test_ask_with_graphrag_handles_generated_cypher_errors(monkeypatch):
    service = QAService()

    class _FailingGraphRAG:
        def search(self, **kwargs):
            raise Text2CypherRetrievalError("bad cypher")

    monkeypatch.setattr(service, "_get_graphrag", lambda: _FailingGraphRAG())

    with pytest.raises(ValueError, match="Failed to execute graph retrieval query: bad cypher"):
        service._ask_with_graphrag(
            question="Who filed claim CLM-2024-PROP-00289?",
            document_ids=None,
            n_context=5,
        )


def test_query_terms_normalizes_tokens_for_graph_matching():
    service = QAService()
    terms = service._query_terms("What locations are mentioned for CLM-2024-PROP-00289?")

    assert "what" not in terms
    assert "locations" in terms
    assert "location" in terms
    assert "clm-2024-prop-00289" in terms
    assert "clm2024prop00289" in terms


def test_question_intent_detects_entity_type_and_relation():
    service = QAService()

    where_intent = service._question_intent("Where is the incident located?")
    assert where_intent == {"intent_type": "Location", "intent_rel": "LOCATED_AT"}

    comms_intent = service._question_intent("Who communicated with ABC Plumbing?")
    assert comms_intent == {"intent_type": "Person", "intent_rel": "COMMUNICATED_WITH"}


@pytest.mark.integration
@pytest.mark.parametrize(
    ("question", "expected_fact"),
    [
        ("What was the total estimate?", "$3,950.00"),
        ("What was the claim number?", "CLM-2024-AUTO-00147"),
        ("Where did the collision occur?", "Interstate 35"),
        ("What was the police report number?", "APD-2024-01547"),
        ("Who is the claimant?", "Robert J. Thompson"),
        ("What is the policy number?", "POL-AUTO-2024-88421"),
        ("What vehicle was involved?", "Toyota Camry"),
        ("What is the VIN?", "4T1BF1FK5CU512847"),
        ("When did the loss occur?", "January 15, 2024"),
        ("What parts need to be replaced?", "Bumper"),
        ("What was the estimated labor cost?", "$960"),
    ],
)
def test_auto_claim_real_retriever(
    question: str,
    expected_fact: str,
):
    """
    REAL integration test - queries actual Neo4j database.
    
    This test requires:
    1. Neo4j to be running
    2. The auto claim document to be ingested
    3. Valid OPENAI_API_KEY to be set (not test key)
    
    To run: pytest -v -s -m integration tests/test_qa_service.py::test_auto_claim_real_retriever
    """
    import os
    
    # Unset test environment variable if it exists to use real .env file
    if "OPENAI_API_KEY" in os.environ and "test" in os.environ["OPENAI_API_KEY"].lower():
        del os.environ["OPENAI_API_KEY"]
    
    # Clear cached settings to pick up .env file
    get_settings.cache_clear()
    
    settings = get_settings()
    
    # Skip if no API key
    if not settings.openai_api_key:
        pytest.skip("This test requires a valid OpenAI API key. Set OPENAI_API_KEY in .env file.")
    
    print(f"Using API key: {settings.openai_api_key[:20]}...")
    
    service = QAService()
    
    print(f"\n{'='*80}")
    print(f"Question: {question}")
    print(f"Expected fact: {expected_fact}")
    
    # Query the REAL database
    result = service.ask(
        question=question,
        document_ids=None,  # Search all documents
        n_context=10,
    )
    
    print(f"\nAnswer: {result['answer']}")
    print(f"Confidence: {result['confidence']:.2%}")
    print(f"\nSources ({len(result['sources'])}):")
    for idx, source in enumerate(result["sources"], start=1):
        print(f"  [{idx}] {source.get('filename', 'Unknown')}: {source.get('excerpt', '')[:150]}...")
    print(f"{'='*80}\n")
    
    # Assertions
    assert result["answer"] != service.NO_EVIDENCE_ANSWER, (
        f"No evidence found for question: {question}"
    )
    assert len(result["sources"]) > 0, "No sources returned"
    
    # Check if expected fact appears in answer or sources
    answer_lower = result["answer"].lower()
    expected_lower = expected_fact.lower()
    
    fact_in_answer = expected_lower in answer_lower
    fact_in_sources = any(
        expected_lower in source.get("excerpt", "").lower()
        for source in result["sources"]
    )
    
    assert fact_in_answer or fact_in_sources, (
        f"Expected fact '{expected_fact}' not found in answer or sources.\n"
        f"Answer: {result['answer']}\n"
        f"Sources: {result['sources']}"
    )
