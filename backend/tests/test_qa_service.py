"""Tests for QA service Text2Cypher behavior."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

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
        }
    ]


def test_ask_with_graphrag_rejects_document_ids_filter(monkeypatch):
    service = QAService()
    fake_rag = _FakeGraphRAG()
    monkeypatch.setattr(service, "_get_graphrag", lambda: fake_rag)

    with pytest.raises(
        ValueError,
        match="document_ids filtering is not supported with Text2CypherRetriever",
    ):
        service._ask_with_graphrag(
            question="Find entities",
            document_ids=["doc-1"],
            n_context=5,
        )

    assert fake_rag.calls == []
