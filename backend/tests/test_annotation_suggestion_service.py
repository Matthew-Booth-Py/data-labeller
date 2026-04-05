import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "uu_backend.django_project.settings.test")
django.setup()

from uu_backend.services.annotation_suggestion_service import AnnotationSuggestionService


@pytest.fixture
def suggestion_service():
    with (
        patch("uu_backend.services.annotation_suggestion_service.get_extraction_service"),
        patch("uu_backend.services.annotation_suggestion_service.get_document_repository"),
    ):
        yield AnnotationSuggestionService()


def test_regions_for_field_falls_back_to_top_level_parent(suggestion_service):
    field_regions = {
        "quarterly_financial_highlights": [
            {"page": 5, "x": 10.0, "y": 40.0, "width": 60.0, "height": 30.0}
        ]
    }

    regions = suggestion_service._regions_for_field(
        "quarterly_financial_highlights.period_1_value",
        field_regions,
    )

    assert regions == field_regions["quarterly_financial_highlights"]


def test_find_text_bbox_prefers_match_inside_allowed_region(suggestion_service):
    lines = [
        {"text": "$13.3", "page": 5, "x": 20.0, "y": 8.0, "width": 6.0, "height": 2.0},
        {"text": "$13.3", "page": 5, "x": 42.0, "y": 66.0, "width": 6.0, "height": 2.0},
    ]
    allowed_regions = [{"page": 5, "x": 35.0, "y": 55.0, "width": 25.0, "height": 20.0}]

    bbox, line_idx = suggestion_service._find_text_bbox(
        "$13.3",
        lines,
        set(),
        allowed_regions=allowed_regions,
    )

    assert line_idx == 1
    assert bbox is not None
    assert bbox["y"] == 66.0


def test_find_text_bbox_matches_wrapped_multi_line_phrase(suggestion_service):
    lines = [
        {"text": "Net", "page": 5, "x": 4.0, "y": 60.5, "width": 2.6, "height": 1.6},
        {"text": "Income", "page": 5, "x": 6.8, "y": 60.5, "width": 5.0, "height": 1.6},
        {"text": "(loss)", "page": 5, "x": 12.1, "y": 60.5, "width": 4.1, "height": 1.6},
        {"text": "Attributable", "page": 5, "x": 16.5, "y": 60.5, "width": 8.3, "height": 1.6},
        {"text": "to", "page": 5, "x": 25.2, "y": 60.5, "width": 1.4, "height": 1.6},
        {"text": "Intel", "page": 5, "x": 27.0, "y": 60.5, "width": 3.2, "height": 1.6},
        {"text": "($B)", "page": 5, "x": 4.0, "y": 62.4, "width": 3.8, "height": 1.6},
    ]
    allowed_regions = [{"page": 5, "x": 0.0, "y": 58.0, "width": 35.0, "height": 8.0}]

    bbox, line_idx = suggestion_service._find_text_bbox(
        "Net Income (loss) Attributable to Intel ($B)",
        lines,
        set(),
        allowed_regions=allowed_regions,
    )

    assert line_idx == 0
    assert bbox is not None
    assert bbox["page"] == 5
    assert bbox["height"] > 3.0


def test_build_field_region_constraints_normalizes_bbox_percentages(suggestion_service):
    page_model = SimpleNamespace(width=1200.0, height=1600.0)
    filter_result = MagicMock()
    filter_result.first.return_value = page_model

    request_metadata = {
        "field_evidence_regions": {
            "quarterly_financial_highlights": [
                {
                    "page_number": 5,
                    "page_id": "page-123",
                    "bbox": [120.0, 320.0, 720.0, 1120.0],
                    "asset_type": "table",
                }
            ]
        }
    }

    with patch(
        "uu_backend.services.annotation_suggestion_service.orm.RetrievalPageModel.objects.filter",
        return_value=filter_result,
    ):
        constraints = suggestion_service._build_field_region_constraints(request_metadata)

    assert constraints["quarterly_financial_highlights"] == [
        {
            "page": 5,
            "x": 10.0,
            "y": 20.0,
            "width": 50.0,
            "height": 50.0,
            "asset_type": "table",
            "asset_label": None,
        }
    ]


def test_create_suggestion_filters_hierarchy_path_to_metric_column(suggestion_service):
    document = SimpleNamespace(id="doc-1")
    positioned_words = [
        {"text": "Net", "page": 5, "x": 4.0, "y": 61.55, "width": 2.0, "height": 1.4},
        {"text": "Income", "page": 5, "x": 6.5, "y": 61.55, "width": 4.4, "height": 1.4},
        {"text": "(loss)", "page": 5, "x": 11.2, "y": 61.55, "width": 3.8, "height": 1.4},
        {"text": "Attributable", "page": 5, "x": 15.3, "y": 61.55, "width": 7.6, "height": 1.4},
        {"text": "to", "page": 5, "x": 23.2, "y": 61.55, "width": 1.2, "height": 1.4},
        {"text": "Intel", "page": 5, "x": 24.8, "y": 61.55, "width": 3.2, "height": 1.4},
        {"text": "$(16.6)", "page": 5, "x": 30.0, "y": 62.0, "width": 5.4, "height": 1.4},
        {"text": "($B)", "page": 5, "x": 4.0, "y": 62.53, "width": 3.0, "height": 1.4},
    ]
    allowed_regions = [{"page": 5, "x": 3.0, "y": 54.0, "width": 90.0, "height": 12.0}]

    suggestion = suggestion_service._create_suggestion(
        document=document,
        field_name="quarterly_financial_highlights.hierarchy_path",
        value=["GAAP", "Net Income (loss) Attributable to Intel ($B)"],
        instance_num=6,
        positioned_words=positioned_words,
        used_line_indices=set(),
        allowed_regions=allowed_regions,
    )

    assert suggestion is not None
    assert suggestion.annotation_data["page"] == 5
    assert suggestion.annotation_data["height"] > 2.0
