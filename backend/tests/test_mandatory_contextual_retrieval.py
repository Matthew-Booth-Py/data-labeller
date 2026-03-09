from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uu_backend.django_project.settings.test")
django.setup()

from django.utils import timezone
from rest_framework.test import APIRequestFactory

from uu_backend.django_api.taxonomy.views import ExtractDocumentView
from uu_backend.models.document import Document, DocumentMetadata
from uu_backend.models.taxonomy import (
    ExtractedField,
    ExtractionRequestMetrics,
    ExtractionResult,
    FieldType,
    SchemaField,
    VisualContentType,
)
from uu_backend.repositories.django_repo import DjangoORMRepository
from uu_backend.ingestion.converter import extract_pdf_with_tables, postprocess_markdown
from uu_backend.services.contextual_retrieval.models import SearchResult
from uu_backend.services.extraction_service import ExtractionService
from uu_backend.tasks.contextual_retrieval_tasks import _load_document_content_for_retrieval


@pytest.fixture
def extraction_service():
    settings = SimpleNamespace(
        effective_tagging_model="gpt-test",
        openai_model_pricing={},
    )
    openai_client = SimpleNamespace(_client=SimpleNamespace())

    with (
        patch("uu_backend.services.extraction_service.get_settings", return_value=settings),
        patch(
            "uu_backend.services.extraction_service.get_openai_client",
            return_value=openai_client,
        ),
    ):
        yield ExtractionService()


def _sample_table_field() -> SchemaField:
    return SchemaField(
        name="supplemental_forward_looking_estimates",
        type=FieldType.ARRAY,
        description="Hierarchical GAAP to Non-GAAP forward-looking estimates reconciliation table",
        extraction_prompt=(
            "Extract ONLY data from the actual reconciliation table. Preserve exact values, "
            "headers, and hierarchy."
        ),
        visual_content_type=VisualContentType.TABLE,
        visual_features=[
            "column header: Full-Year 2024",
            "column header: Full-Year 2025",
            "row label: Non-GAAP net capital spending",
            "data type: currency_range",
        ],
        items=SchemaField(
            name="supplemental_forward_looking_estimates_item",
            type=FieldType.OBJECT,
            properties={
                "hierarchy_path": SchemaField(
                    name="hierarchy_path",
                    type=FieldType.ARRAY,
                    items=SchemaField(name="hierarchy_path_item", type=FieldType.STRING),
                ),
                "period_1_header": SchemaField(name="period_1_header", type=FieldType.STRING),
                "period_1_value": SchemaField(name="period_1_value", type=FieldType.STRING),
                "period_2_header": SchemaField(name="period_2_header", type=FieldType.STRING),
                "period_2_value": SchemaField(name="period_2_value", type=FieldType.STRING),
            },
        ),
    )


def _sample_scalar_field() -> SchemaField:
    return SchemaField(
        name="company_name",
        type=FieldType.STRING,
        description="Legal company name from the filing",
        extraction_prompt="Extract the exact company name as shown in the document.",
    )


def _sample_request_metrics() -> ExtractionRequestMetrics:
    return ExtractionRequestMetrics(
        request_id="req-1",
        schema_version_id="schema-1",
        prompt_version_id=None,
        model="gpt-test",
        latency_ms=1234,
        prompt_tokens=100,
        completion_tokens=50,
        total_tokens=150,
        cost_usd=None,
        cost_note=None,
        created_at=timezone.now(),
    )


def _sample_extraction_result() -> ExtractionResult:
    return ExtractionResult(
        document_id="doc-1",
        document_type_id="type-1",
        fields=[
            ExtractedField(
                field_name="company_name",
                value="INTEL CORPORATION",
                confidence=0.95,
                source_text="Pages: [17]",
            )
        ],
        requests=[_sample_request_metrics()],
        request_metadata={"strategy": "contextual_retrieval_vision", "source_page_numbers": [17]},
        schema_version_id="schema-1",
        prompt_version_id=None,
        extracted_at=timezone.now(),
        source_page_numbers=[17],
    )


def _intc_8k_pdf_path() -> Path:
    pdf_path = Path(__file__).resolve().parents[2] / "docs" / "intc-8k.pdf"
    assert pdf_path.exists(), f"Missing regression fixture: {pdf_path}"
    return pdf_path


@lru_cache(maxsize=1)
def _intc_8k_pdf_content() -> str:
    content, _ = extract_pdf_with_tables(str(_intc_8k_pdf_path()))
    return postprocess_markdown(content)


def _expected_intc_forward_looking_estimates_payload() -> list[dict[str, object]]:
    period_1_header = "Full-Year 2024 Approximately"
    period_2_header = "Full-Year 2025 Approximately"

    return [
        {
            "hierarchy_path": [
                "GAAP additions to property, plant and equipment (gross capital expenditures)"
            ],
            "period_1_header": period_1_header,
            "period_1_value": "$ 25.0",
            "period_2_header": period_2_header,
            "period_2_value": "$20.0 - $23.0",
        },
        {
            "hierarchy_path": [
                "GAAP additions to property, plant and equipment (gross capital expenditures)",
                "Proceeds from capital-related government incentives",
            ],
            "period_1_header": period_1_header,
            "period_1_value": "(1.0)",
            "period_2_header": period_2_header,
            "period_2_value": "(4.0 - 6.0)",
        },
        {
            "hierarchy_path": [
                "GAAP additions to property, plant and equipment (gross capital expenditures)",
                "Partner contributions, net",
            ],
            "period_1_header": period_1_header,
            "period_1_value": "(13.0)",
            "period_2_header": period_2_header,
            "period_2_value": "(4.0 - 5.0)",
        },
        {
            "hierarchy_path": ["Non-GAAP net capital spending"],
            "period_1_header": period_1_header,
            "period_1_value": "$      11.0",
            "period_2_header": period_2_header,
            "period_2_value": "$12.0 - $14.0",
        },
        {
            "hierarchy_path": ["GAAP R&D and MG&A"],
            "period_1_header": period_1_header,
            "period_1_value": None,
            "period_2_header": period_2_header,
            "period_2_value": "$      20.0",
        },
        {
            "hierarchy_path": ["GAAP R&D and MG&A", "Acquisition-related adjustments"],
            "period_1_header": period_1_header,
            "period_1_value": None,
            "period_2_header": period_2_header,
            "period_2_value": "(0.1)",
        },
        {
            "hierarchy_path": ["GAAP R&D and MG&A", "Share-based compensation"],
            "period_1_header": period_1_header,
            "period_1_value": None,
            "period_2_header": period_2_header,
            "period_2_value": "(2.4)",
        },
        {
            "hierarchy_path": ["Non-GAAP R&D and MG&A"],
            "period_1_header": period_1_header,
            "period_1_value": None,
            "period_2_header": period_2_header,
            "period_2_value": "$      17.5",
        },
    ]


def test_load_document_content_for_retrieval_uses_layout_preserving_pdf_extractor(tmp_path):
    pdf_path = tmp_path / "intc-8k.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")
    document = Document(
        id="doc-1",
        filename="intc-8k.pdf",
        file_type="pdf",
        content="stored fallback content",
        metadata=DocumentMetadata(filename="intc-8k.pdf", file_type="pdf"),
        file_path=str(pdf_path),
    )

    with (
        patch(
            "uu_backend.tasks.contextual_retrieval_tasks.extract_pdf_with_tables",
            return_value=("## Page 17\n\nfinancial table", 1),
        ) as extract_pdf,
        patch(
            "uu_backend.tasks.contextual_retrieval_tasks.postprocess_markdown",
            side_effect=lambda content: content,
        ) as postprocess,
    ):
        content = _load_document_content_for_retrieval(document)

    extract_pdf.assert_called_once_with(str(pdf_path))
    postprocess.assert_called_once()
    assert content.startswith("## Page 17")


def test_build_field_queries_include_doc_context_prompt_and_visual_cues(extraction_service):
    doc_type = SimpleNamespace(
        name="8-K Filing",
        description="Public company current report describing forward-looking estimates",
    )
    field = _sample_table_field()

    queries = extraction_service._build_field_queries(doc_type, field)

    assert len(queries) >= 3
    assert any("8-K Filing" in query for query in queries)
    assert any(doc_type.description in query for query in queries)
    assert any("actual reconciliation table" in query for query in queries)
    assert any("column header: Full-Year 2024" in query for query in queries)
    assert any("row label: Non-GAAP net capital spending" in query for query in queries)


def test_ensure_retrieval_ready_rejects_pending_and_failed_statuses(extraction_service):
    pending_document = SimpleNamespace(retrieval_index_status="pending", retrieval_chunks_count=None)
    failed_document = SimpleNamespace(retrieval_index_status="failed", retrieval_chunks_count=None)

    with pytest.raises(ValueError, match="required before extraction"):
        extraction_service._ensure_retrieval_ready(pending_document)

    with pytest.raises(ValueError, match="failed for this document"):
        extraction_service._ensure_retrieval_ready(failed_document)


def test_extract_structured_with_retrieval_vision_selects_page_17_and_returns_rows(
    extraction_service, tmp_path
):
    pdf_path = tmp_path / "intc-8k.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n")

    company_field = _sample_scalar_field()
    table_field = _sample_table_field()
    document = Document(
        id="doc-1",
        filename="intc-8k.pdf",
        file_type="pdf",
        content="## Page 1\n\nCover\n\n## Page 17\n\nTable",
        metadata=DocumentMetadata(filename="intc-8k.pdf", file_type="pdf"),
        file_path=str(pdf_path),
        retrieval_index_status="completed",
        retrieval_chunks_count=8,
    )

    repository = MagicMock()
    repository.get_classification.return_value = SimpleNamespace(document_type_id="type-1")
    repository.get_document_type.return_value = SimpleNamespace(
        id="type-1",
        name="8-K Filing",
        description="Forward-looking estimates and reconciliation tables",
        schema_fields=[company_field, table_field],
        system_prompt="Extract filing data",
        schema_version_id="schema-1",
        extraction_model=None,
    )
    repository.list_active_field_prompt_versions.return_value = {}
    repository.get_prompt_version.return_value = None

    document_repo = MagicMock()
    document_repo.get_document.return_value = document

    def search(query: str, top_k: int, filter_doc_id: str, use_reranking: bool):
        _ = top_k, filter_doc_id, use_reranking
        if "company name" in query.lower():
            return [
                SearchResult(
                    doc_id="doc-1",
                    chunk_index=1,
                    text="Intel page 1",
                    original_text="Intel page 1",
                    context="cover",
                    score=0.4,
                    metadata={"page_number": 1, "page_summary": "Cover page"},
                ),
                SearchResult(
                    doc_id="doc-1",
                    chunk_index=17,
                    text="Intel page 17",
                    original_text="Intel page 17",
                    context="table",
                    score=0.7,
                    metadata={"page_number": 17, "page_summary": "Forward-looking table"},
                ),
            ]

        return [
            SearchResult(
                doc_id="doc-1",
                chunk_index=170,
                text="Table chunk A",
                original_text="Table chunk A",
                context="table",
                score=0.98,
                metadata={"page_number": 17, "page_summary": "Forward-looking table"},
            ),
            SearchResult(
                doc_id="doc-1",
                chunk_index=171,
                text="Table chunk B",
                original_text="Table chunk B",
                context="table",
                score=0.83,
                metadata={"page_number": 17, "page_summary": "Forward-looking table"},
            ),
            SearchResult(
                doc_id="doc-1",
                chunk_index=160,
                text="Nearby chunk",
                original_text="Nearby chunk",
                context="table",
                score=0.62,
                metadata={"page_number": 16, "page_summary": "Nearby discussion"},
            ),
        ]

    retrieval_service = MagicMock()
    retrieval_service.search.side_effect = search

    rendered_pages: list[int] = []

    def fake_render_pdf_pages(file_path, page_numbers, dpi=150):
        _ = file_path, dpi
        rendered_pages[:] = page_numbers
        return ["page-image" for _ in page_numbers]

    def fake_parse_with_metrics(**kwargs):
        response_format = kwargs["response_format"]
        parsed = response_format.model_validate(
            {
                "company_name": "INTEL CORPORATION",
                "supplemental_forward_looking_estimates": [
                    {
                        "hierarchy_path": ["Non-GAAP net capital spending"],
                        "period_1_header": "Full-Year 2024 (Approximately)",
                        "period_1_value": "$ 11.0",
                        "period_2_header": "Full-Year 2025 (Approximately)",
                        "period_2_value": "$12.0 - $14.0",
                    }
                ],
            }
        )
        return parsed, _sample_request_metrics()

    extraction_service._render_pdf_pages = fake_render_pdf_pages
    extraction_service._parse_with_metrics = fake_parse_with_metrics
    extraction_service._save_extraction = lambda result: None

    with (
        patch("uu_backend.services.extraction_service.get_repository", return_value=repository),
        patch(
            "uu_backend.services.extraction_service.get_document_repository",
            return_value=document_repo,
        ),
        patch(
            "uu_backend.services.contextual_retrieval.get_contextual_retrieval_service",
            return_value=retrieval_service,
        ),
    ):
        result = extraction_service.extract_structured_with_retrieval_vision("doc-1")

    extracted_fields = {field.field_name: field.value for field in result.fields}
    assert "supplemental_forward_looking_estimates" in extracted_fields
    assert extracted_fields["supplemental_forward_looking_estimates"] != []
    assert 17 in result.source_page_numbers
    assert result.request_metadata == {
        "strategy": "contextual_retrieval_vision",
        "source_page_numbers": [1, 16, 17],
    }
    assert 2 <= len(rendered_pages) <= 4
    assert 17 in rendered_pages


def test_single_schema_field_returns_full_intc_forward_looking_estimates_payload(
    extraction_service,
):
    table_field = _sample_table_field()
    expected_payload = _expected_intc_forward_looking_estimates_payload()
    document = Document(
        id="doc-1",
        filename="intc-8k.pdf",
        file_type="pdf",
        content=_intc_8k_pdf_content(),
        metadata=DocumentMetadata(filename="intc-8k.pdf", file_type="pdf"),
        file_path=str(_intc_8k_pdf_path()),
        retrieval_index_status="completed",
        retrieval_chunks_count=24,
    )

    repository = MagicMock()
    repository.get_classification.return_value = SimpleNamespace(document_type_id="type-1")
    repository.get_document_type.return_value = SimpleNamespace(
        id="type-1",
        name="8-K Filing",
        description="Public company current report describing forward-looking estimate tables",
        schema_fields=[table_field],
        system_prompt="Extract filing data",
        schema_version_id="schema-1",
        extraction_model=None,
    )
    repository.list_active_field_prompt_versions.return_value = {}
    repository.get_prompt_version.return_value = None

    document_repo = MagicMock()
    document_repo.get_document.return_value = document

    retrieval_service = MagicMock()
    retrieval_service.search.return_value = [
        SearchResult(
            doc_id="doc-1",
            chunk_index=210,
            text="Forward-looking estimate reconciliation table",
            original_text="Forward-looking estimate reconciliation table",
            context="table",
            score=0.99,
            metadata={"page_number": 21, "page_summary": "Intel reconciliation table"},
        ),
        SearchResult(
            doc_id="doc-1",
            chunk_index=209,
            text="Lead-in paragraph before the table",
            original_text="Lead-in paragraph before the table",
            context="table",
            score=0.64,
            metadata={"page_number": 20, "page_summary": "Preceding page"},
        ),
        SearchResult(
            doc_id="doc-1",
            chunk_index=211,
            text="Contacts after the table",
            original_text="Contacts after the table",
            context="table",
            score=0.58,
            metadata={"page_number": 22, "page_summary": "Following page"},
        ),
    ]

    rendered_pages: list[int] = []

    def fake_render_pdf_pages(file_path, page_numbers, dpi=150):
        _ = file_path, dpi
        rendered_pages[:] = page_numbers
        return [f"page-{page_number}" for page_number in page_numbers]

    def fake_parse_with_metrics(**kwargs):
        response_format = kwargs["response_format"]
        parsed = response_format.model_validate(
            {"supplemental_forward_looking_estimates": expected_payload}
        )
        return parsed, _sample_request_metrics()

    extraction_service._render_pdf_pages = fake_render_pdf_pages
    extraction_service._parse_with_metrics = fake_parse_with_metrics
    extraction_service._save_extraction = lambda result: None

    with (
        patch("uu_backend.services.extraction_service.get_repository", return_value=repository),
        patch(
            "uu_backend.services.extraction_service.get_document_repository",
            return_value=document_repo,
        ),
        patch(
            "uu_backend.services.contextual_retrieval.get_contextual_retrieval_service",
            return_value=retrieval_service,
        ),
    ):
        result = extraction_service.extract_structured_with_retrieval_vision("doc-1")

    extracted_fields = {field.field_name: field.value for field in result.fields}
    assert extracted_fields == {
        "supplemental_forward_looking_estimates": expected_payload,
    }
    assert result.request_metadata == {
        "strategy": "contextual_retrieval_vision",
        "source_page_numbers": [20, 21],
    }
    assert result.source_page_numbers == [20, 21]
    assert set(rendered_pages) == {20, 21}


def test_intc_8k_pdf_extraction_preserves_all_forward_looking_estimate_table_items():
    content = _intc_8k_pdf_content()

    page_marker = "## Page 21"
    assert page_marker in content
    page_start = content.index(page_marker)
    page_end = content.find("## Page 22", page_start)
    page_text = content[page_start : page_end if page_end != -1 else None]

    expected_rows = [
        (
            "GAAP additions to property, plant and equipment (gross capital expenditures)",
            "$ 25.0",
            "$20.0 - $23.0",
        ),
        (
            "Proceeds from capital-related government incentives",
            "(1.0)",
            "(4.0 - 6.0)",
        ),
        (
            "Partner contributions, net",
            "(13.0)",
            "(4.0 - 5.0)",
        ),
        (
            "Non-GAAP net capital spending",
            "$      11.0",
            "$12.0 - $14.0",
        ),
        ("GAAP R&D and MG&A", "$      20.0", None),
        ("Acquisition-related adjustments", "(0.1)", None),
        ("Share-based compensation", "(2.4)", None),
        ("Non-GAAP R&D and MG&A", "$      17.5", None),
    ]

    assert "Full-Year 2024 Full-Year 2025" in page_text
    assert "Approximately Approximately" in page_text

    for label, first_value, second_value in expected_rows:
        assert label in page_text
        assert first_value in page_text
        if second_value is not None:
            assert second_value in page_text


def test_extract_document_view_rejects_non_retrieval_requests():
    factory = APIRequestFactory()
    request = factory.post("/api/v1/taxonomy/documents/doc-1/extract")

    with patch("uu_backend.django_api.taxonomy.views.get_extraction_service") as service_factory:
        response = ExtractDocumentView.as_view()(request, document_id="doc-1")

    assert response.status_code == 400
    assert "Contextual retrieval is mandatory" in response.data["detail"]
    service_factory.return_value.extract_structured_with_retrieval_vision.assert_not_called()


def test_extract_document_view_returns_retrieval_result_for_indexed_document():
    factory = APIRequestFactory()
    request = factory.post("/api/v1/taxonomy/documents/doc-1/extract?use_retrieval=true")
    service = MagicMock()
    service.extract_structured_with_retrieval_vision.return_value = _sample_extraction_result()
    repository = MagicMock()
    repository.get_extraction.return_value = None

    with (
        patch("uu_backend.django_api.taxonomy.views.get_extraction_service", return_value=service),
        patch("uu_backend.django_api.taxonomy.views.get_repository", return_value=repository),
    ):
        response = ExtractDocumentView.as_view()(request, document_id="doc-1")

    assert response.status_code == 200
    assert response.data["document_id"] == "doc-1"
    assert response.data["request_metadata"] == {
        "strategy": "contextual_retrieval_vision",
        "source_page_numbers": [17],
    }
    service.extract_structured_with_retrieval_vision.assert_called_once_with("doc-1")


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        (
            "Contextual retrieval indexing is required before extraction. Index or reindex this document and retry.",
            "required before extraction",
        ),
        (
            "Contextual retrieval indexing failed for this document. Reindex the document before running extraction.",
            "failed for this document",
        ),
    ],
)
def test_extract_document_view_returns_clear_retrieval_errors(message, expected):
    factory = APIRequestFactory()
    request = factory.post("/api/v1/taxonomy/documents/doc-1/extract?use_retrieval=true")
    service = MagicMock()
    service.extract_structured_with_retrieval_vision.side_effect = ValueError(message)

    with patch("uu_backend.django_api.taxonomy.views.get_extraction_service", return_value=service):
        response = ExtractDocumentView.as_view()(request, document_id="doc-1")

    assert response.status_code == 400
    assert expected in response.data["detail"]


def test_save_extraction_result_persists_request_metadata():
    repository = DjangoORMRepository()
    result = _sample_extraction_result()
    empty_queryset = MagicMock()
    empty_queryset.first.return_value = None

    with (
        patch(
            "uu_backend.repositories.django_repo.orm.ExtractionModel.objects.filter",
            return_value=empty_queryset,
        ),
        patch("uu_backend.repositories.django_repo.orm.ExtractionModel.objects.create") as create,
    ):
        repository.save_extraction_result(result)

    assert create.call_args.kwargs["request_metadata"] == {
        "strategy": "contextual_retrieval_vision",
        "source_page_numbers": [17],
    }
