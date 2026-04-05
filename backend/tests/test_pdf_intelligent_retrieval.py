import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uu_backend.django_project.settings.test")
django.setup()

from uu_backend.models.taxonomy import FieldType, SchemaField, VisualContentType
from uu_backend.services.contextual_retrieval.models import SearchResult
from uu_backend.services.extraction_service import ExtractionService
from uu_backend.services.pdf_retrieval import PDF_RETRIEVAL_BACKEND
from uu_backend.services.pdf_retrieval.document_intelligence import NormalizedLine, NormalizedPage
from uu_backend.services.pdf_retrieval.service import PDFRetrievalService


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
        name="line_items",
        type=FieldType.ARRAY,
        description="Financial reconciliation table",
        extraction_prompt="Extract rows from the actual reconciliation table.",
        visual_content_type=VisualContentType.TABLE,
        items=SchemaField(
            name="line_item",
            type=FieldType.OBJECT,
            properties={
                "hierarchy_path": SchemaField(
                    name="hierarchy_path",
                    type=FieldType.ARRAY,
                    items=SchemaField(name="path_item", type=FieldType.STRING),
                )
            },
        ),
    )


def _sample_scalar_field() -> SchemaField:
    return SchemaField(
        name="company_name",
        type=FieldType.STRING,
        description="Legal company name",
        extraction_prompt="Extract the exact company name.",
    )


def test_ensure_retrieval_ready_requires_pdf_backend_upgrade(extraction_service):
    legacy_document = SimpleNamespace(
        file_type="pdf",
        retrieval_index_status="completed",
        retrieval_chunks_count=10,
        retrieval_index_backend="legacy_contextual_v1",
    )

    with pytest.raises(ValueError, match="legacy retrieval backend"):
        extraction_service._ensure_retrieval_ready(legacy_document)


def test_ensure_retrieval_ready_rejects_non_pdf(extraction_service):
    document = SimpleNamespace(
        file_type="docx",
        retrieval_index_status="completed",
        retrieval_chunks_count=10,
        retrieval_index_backend=PDF_RETRIEVAL_BACKEND,
    )

    with pytest.raises(ValueError, match="PDF-only intelligent retrieval"):
        extraction_service._ensure_retrieval_ready(document)


def test_agentic_retrieval_loop_retries_until_field_is_covered(extraction_service):
    retrieval_service = MagicMock()
    retrieval_service.search_for_extraction.side_effect = [
        [],
        [
            SearchResult(
                doc_id="doc-1",
                chunk_index=1,
                text="Intel Corporation",
                original_text="Intel Corporation",
                context="",
                score=0.92,
                metadata={"page_number": 1},
                chunk_id="chunk-1",
                page_number=1,
                asset_type="page",
                asset_label="Page 1",
            )
        ],
    ]

    doc_type = SimpleNamespace(name="10-K", description="Annual report")
    field = _sample_scalar_field()

    with patch.object(
        extraction_service,
        "_generate_follow_up_queries",
        return_value=["exact legal entity name"],
    ):
        evidence_by_field, coverage_by_field, retry_count = extraction_service._run_agentic_retrieval_loop(
            document_id="doc-1",
            doc_type=doc_type,
            schema_fields=[field],
            retrieval_service=retrieval_service,
            top_k_per_field=2,
        )

    assert retry_count == 1
    assert coverage_by_field["company_name"]["status"] == "covered"
    assert evidence_by_field["company_name"][0].chunk_id == "chunk-1"


def test_select_pages_from_evidence_keeps_multi_page_table_ranges(extraction_service):
    table_result = SearchResult(
        doc_id="doc-1",
        chunk_index=2,
        text="Table summary",
        original_text="| header |",
        context="Summary",
        score=0.88,
        metadata={"page_numbers": [17, 18], "page_number": 17},
        chunk_id="chunk-table",
        page_number=17,
        asset_type="table",
        asset_label="Table 1 on pages 17-18",
    )
    scalar_result = SearchResult(
        doc_id="doc-1",
        chunk_index=3,
        text="Intel Corporation",
        original_text="Intel Corporation",
        context="",
        score=0.72,
        metadata={"page_number": 1},
        chunk_id="chunk-page",
        page_number=1,
        asset_type="page",
        asset_label="Page 1",
    )

    schema_fields = [_sample_table_field(), _sample_scalar_field()]
    evidence_by_field = {
        "line_items": [table_result],
        "company_name": [scalar_result],
    }

    selected_pages, field_page_map = extraction_service._select_pages_from_evidence(
        schema_fields=schema_fields,
        evidence_by_field=evidence_by_field,
    )

    assert set(selected_pages) >= {1, 17, 18}
    assert field_page_map["line_items"] == {17, 18}


def test_select_pages_from_evidence_anchors_table_field_to_top_match(extraction_service):
    primary_table_result = SearchResult(
        doc_id="doc-1",
        chunk_index=10,
        text="Quarterly Financial Highlights",
        original_text="Quarterly Financial Highlights",
        context="",
        score=0.93,
        metadata={"page_numbers": [5], "page_number": 5},
        chunk_id="chunk-table-5",
        page_number=5,
        asset_type="table",
        asset_label="Table 3 on page 5",
    )
    similar_table_result = SearchResult(
        doc_id="doc-1",
        chunk_index=11,
        text="Supplemental Reconciliations",
        original_text="Supplemental Reconciliations",
        context="",
        score=0.89,
        metadata={"page_numbers": [18], "page_number": 18},
        chunk_id="chunk-table-18",
        page_number=18,
        asset_type="table",
        asset_label="Table 14 on page 18",
    )

    selected_pages, field_page_map = extraction_service._select_pages_from_evidence(
        schema_fields=[_sample_table_field()],
        evidence_by_field={"line_items": [primary_table_result, similar_table_result]},
    )

    assert selected_pages == [5]
    assert field_page_map["line_items"] == {5}


def test_filter_evidence_to_selected_pages_drops_unrelated_table_hits(extraction_service):
    primary_table_result = SearchResult(
        doc_id="doc-1",
        chunk_index=10,
        text="Quarterly Financial Highlights",
        original_text="Quarterly Financial Highlights",
        context="",
        score=0.93,
        metadata={"page_numbers": [5], "page_number": 5},
        chunk_id="chunk-table-5",
        page_number=5,
        asset_type="table",
        asset_label="Table 3 on page 5",
    )
    similar_table_result = SearchResult(
        doc_id="doc-1",
        chunk_index=11,
        text="Supplemental Reconciliations",
        original_text="Supplemental Reconciliations",
        context="",
        score=0.89,
        metadata={"page_numbers": [18], "page_number": 18},
        chunk_id="chunk-table-18",
        page_number=18,
        asset_type="table",
        asset_label="Table 14 on page 18",
    )

    filtered = extraction_service._filter_evidence_to_selected_pages(
        schema_fields=[_sample_table_field()],
        evidence_by_field={"line_items": [primary_table_result, similar_table_result]},
        field_page_map={"line_items": {5}},
    )

    assert [result.chunk_id for result in filtered["line_items"]] == ["chunk-table-5"]


def test_build_field_evidence_regions_only_emits_table_regions(extraction_service):
    table_result = SearchResult(
        doc_id="doc-1",
        chunk_index=10,
        text="Quarterly Financial Highlights",
        original_text="Quarterly Financial Highlights",
        context="",
        score=0.93,
        metadata={"page_numbers": [5], "page_number": 5},
        chunk_id="chunk-table-5",
        page_number=5,
        asset_type="table",
        asset_label="Table 3 on page 5",
        citation_regions=[
            {
                "page_number": 5,
                "page_id": "page-5",
                "bbox": [10.0, 20.0, 30.0, 40.0],
                "preview_artifact_id": "artifact-1",
            }
        ],
    )
    image_result = SearchResult(
        doc_id="doc-1",
        chunk_index=11,
        text="Intel logo",
        original_text="Intel logo",
        context="",
        score=0.95,
        metadata={"page_number": 1},
        chunk_id="chunk-image-1",
        page_number=1,
        asset_type="image",
        asset_label="Image 1 on page 1",
        citation_regions=[
            {
                "page_number": 1,
                "page_id": "page-1",
                "bbox": [1.0, 2.0, 3.0, 4.0],
                "preview_artifact_id": "artifact-2",
            }
        ],
    )

    field_regions = extraction_service._build_field_evidence_regions(
        schema_fields=[_sample_table_field(), _sample_scalar_field()],
        evidence_by_field={
            "line_items": [table_result],
            "company_name": [image_result],
        },
    )

    assert field_regions == {
        "line_items": [
            {
                "page_number": 5,
                "page_id": "page-5",
                "bbox": [10.0, 20.0, 30.0, 40.0],
                "preview_artifact_id": "artifact-1",
                "asset_type": "table",
                "asset_label": "Table 3 on page 5",
            }
        ]
    }


def test_table_fields_only_prefer_table_assets(extraction_service):
    assert extraction_service._preferred_asset_types_for_field(_sample_table_field()) == {"table"}
    assert extraction_service._preferred_asset_types_for_field(_sample_scalar_field()) == {
        "image",
        "page",
        "table",
    }


def test_table_heading_context_prefers_lines_immediately_above_table():
    service = PDFRetrievalService.__new__(PDFRetrievalService)
    page = NormalizedPage(
        page_number=1,
        width=1000.0,
        height=1400.0,
        text="",
        lines=[
            NormalizedLine(
                text="Intel Reports Third-Quarter 2024 Financial Results",
                bbox=[80.0, 40.0, 760.0, 70.0],
            ),
            NormalizedLine(
                text="NEWS SUMMARY",
                bbox=[80.0, 90.0, 260.0, 115.0],
            ),
            NormalizedLine(
                text="Q3 2024 Financial Highlights",
                bbox=[80.0, 600.0, 360.0, 626.0],
            ),
            NormalizedLine(
                text="(In Billions)",
                bbox=[80.0, 632.0, 220.0, 652.0],
            ),
        ],
    )

    heading_context = service._table_heading_context(
        page=page,
        bbox=[80.0, 670.0, 920.0, 1080.0],
    )

    assert "Q3 2024 Financial Highlights" in heading_context
    assert "(In Billions)" in heading_context
    assert "NEWS SUMMARY" not in heading_context
