"""Tests for the evaluation service and annotation suggestion service.

This test suite covers:
1. Hierarchy_path matching between different formats (string vs array)
2. Proper flattening of extraction results (keeping leaf arrays atomic)
3. Schema compatibility between predictions and ground truth

The goal is to ensure predictions and ground truth use the EXACT SAME SCHEMA
so evaluation compares apples to apples.
"""

import pytest
from unittest.mock import MagicMock, patch

from uu_backend.services.evaluation_service import EvaluationService


class TestNormalizeHierarchyToArray:
    """Tests for normalizing hierarchy_path values to arrays."""
    
    @pytest.fixture
    def service(self):
        with patch('uu_backend.services.evaluation_service.get_extraction_service'), \
             patch('uu_backend.services.evaluation_service.get_document_repository'), \
             patch('uu_backend.services.evaluation_service.get_openai_client'):
            return EvaluationService()
    
    def test_normalize_array_passthrough(self, service):
        """Arrays should pass through unchanged."""
        result = service._normalize_hierarchy_to_array(["A", "B", "C"])
        assert result == ["A", "B", "C"]
    
    def test_normalize_comma_separated_string(self, service):
        """Comma-separated strings (no space after comma) should be split into arrays."""
        result = service._normalize_hierarchy_to_array("GAAP additions,Proceeds from capital")
        assert result == ["GAAP additions", "Proceeds from capital"]
    
    def test_normalize_preserves_text_with_comma(self, service):
        """Commas that are part of text (followed by space) should NOT be split."""
        result = service._normalize_hierarchy_to_array("Partner contributions, net")
        assert result == ["Partner contributions, net"]
    
    def test_normalize_real_world_example(self, service):
        """Real-world stringified array should be parsed correctly."""
        value = "GAAP additions to property, plant and equipment (gross capital expenditures),Proceeds from capital-related government incentives"
        result = service._normalize_hierarchy_to_array(value)
        assert result == [
            "GAAP additions to property, plant and equipment (gross capital expenditures)",
            "Proceeds from capital-related government incentives"
        ]
    
    def test_normalize_single_string(self, service):
        """Single strings without commas should become single-element arrays."""
        result = service._normalize_hierarchy_to_array("GAAP additions")
        assert result == ["GAAP additions"]
    
    def test_normalize_none(self, service):
        """None should return empty array."""
        result = service._normalize_hierarchy_to_array(None)
        assert result == []
    
    def test_normalize_empty_string(self, service):
        """Empty string should return empty array."""
        result = service._normalize_hierarchy_to_array("")
        assert result == []


class TestCompareHierarchyValues:
    """Tests for comparing hierarchy_path values with backwards compatibility."""
    
    @pytest.fixture
    def service(self):
        with patch('uu_backend.services.evaluation_service.get_extraction_service'), \
             patch('uu_backend.services.evaluation_service.get_document_repository'), \
             patch('uu_backend.services.evaluation_service.get_openai_client'):
            return EvaluationService()
    
    def test_compare_array_to_array_exact(self, service):
        """Identical arrays should match."""
        assert service._compare_hierarchy_values(
            ["GAAP additions", "Proceeds from capital"],
            ["GAAP additions", "Proceeds from capital"]
        ) is True
    
    def test_compare_comma_string_to_array(self, service):
        """Comma-separated GT string should match pred array."""
        assert service._compare_hierarchy_values(
            "GAAP additions,Proceeds from capital",  # Old format (stringified)
            ["GAAP additions", "Proceeds from capital"]  # New format (array)
        ) is True
    
    def test_compare_single_string_to_single_array(self, service):
        """Single string GT should match single-element pred array."""
        assert service._compare_hierarchy_values(
            "GAAP additions",
            ["GAAP additions"]
        ) is True
    
    def test_compare_leaf_string_to_full_path(self, service):
        """Leaf-only GT string should match last element of pred array."""
        assert service._compare_hierarchy_values(
            "Proceeds from capital",  # Leaf only
            ["GAAP additions", "Proceeds from capital"]  # Full path
        ) is True
    
    def test_compare_non_matching(self, service):
        """Non-matching values should not match."""
        assert service._compare_hierarchy_values(
            "Something else",
            ["GAAP additions", "Proceeds from capital"]
        ) is False
    
    def test_compare_case_insensitive(self, service):
        """Comparison should be case-insensitive."""
        assert service._compare_hierarchy_values(
            "GAAP ADDITIONS,PROCEEDS FROM CAPITAL",
            ["gaap additions", "proceeds from capital"]
        ) is True


class TestHierarchyPathMatching:
    """Tests for hierarchy_path matching between GT strings and prediction arrays."""
    
    @pytest.fixture
    def service(self):
        """Create evaluation service with mocked dependencies."""
        with patch('uu_backend.services.evaluation_service.get_extraction_service'), \
             patch('uu_backend.services.evaluation_service.get_document_repository'), \
             patch('uu_backend.services.evaluation_service.get_openai_client'):
            return EvaluationService()
    
    def test_hierarchy_matches_string_exact_single_element(self, service):
        """Array with single element should match equal string."""
        assert service._hierarchy_matches_string(["GAAP R&D"], "GAAP R&D") is True
        assert service._hierarchy_matches_string(["GAAP R&D"], "gaap r&d") is True  # Case insensitive
        assert service._hierarchy_matches_string(["GAAP R&D"], "Something else") is False
    
    def test_hierarchy_matches_string_leaf_match(self, service):
        """String should match last element (leaf) of multi-element array."""
        assert service._hierarchy_matches_string(
            ["GAAP additions", "Proceeds from capital-related"],
            "Proceeds from capital-related"
        ) is True
        
        assert service._hierarchy_matches_string(
            ["GAAP R&D and MG&A", "Acquisition-related adjustments"],
            "Acquisition-related adjustments"
        ) is True
        
        # Should NOT match non-leaf elements
        assert service._hierarchy_matches_string(
            ["GAAP additions", "Proceeds from capital-related"],
            "GAAP additions"
        ) is False
    
    def test_hierarchy_matches_string_deep_nesting(self, service):
        """Deeply nested hierarchies should match leaf."""
        assert service._hierarchy_matches_string(
            ["Level 1", "Level 2", "Level 3", "Level 4"],
            "Level 4"
        ) is True
        
        # Non-leaf shouldn't match
        assert service._hierarchy_matches_string(
            ["Level 1", "Level 2", "Level 3", "Level 4"],
            "Level 2"
        ) is False
    
    def test_hierarchy_matches_string_whitespace_handling(self, service):
        """Should handle whitespace variations."""
        assert service._hierarchy_matches_string(
            ["GAAP R&D", "  Share-based compensation  "],
            "Share-based compensation"
        ) is True


class TestRowMatchScoring:
    """Tests for row matching score calculation."""
    
    @pytest.fixture
    def service(self):
        """Create evaluation service with mocked dependencies."""
        with patch('uu_backend.services.evaluation_service.get_extraction_service'), \
             patch('uu_backend.services.evaluation_service.get_document_repository'), \
             patch('uu_backend.services.evaluation_service.get_openai_client'):
            return EvaluationService()
    
    def test_calculate_row_match_score_string_gt_to_array_pred(self, service):
        """
        Critical test: GT hierarchy_path is a string, pred hierarchy_path is an array.
        This is the backwards compatibility case.
        """
        # GT group: user labeled hierarchy_path as a single string (leaf node)
        gt_group = [
            {
                "field_name": "forward_looking_estimates_table.hierarchy_path",
                "value": "Proceeds from capital-related government incentives"
            },
            {
                "field_name": "forward_looking_estimates_table.period_1_value",
                "value": "(1.0)"
            },
            {
                "field_name": "forward_looking_estimates_table.period_2_value",
                "value": "(4.0 - 6.0)"
            }
        ]
        
        # Predicted row: hierarchy_path is an array (full path)
        pred_row = {
            "instance": 2,
            "fields": {
                "hierarchy_path": [
                    "GAAP additions to property, plant and equipment (gross capital expenditures)",
                    "Proceeds from capital-related government incentives"
                ],
                "period_1_value": "(1.0)",
                "period_2_value": "(4.0 - 6.0)"
            }
        }
        
        score = service._calculate_row_match_score(
            gt_group, pred_row, "forward_looking_estimates_table"
        )
        
        # Should get a high score since hierarchy (leaf match) + values match
        assert score > 0.5, f"Expected high match score, got {score}"
    
    def test_calculate_row_match_score_top_level_row(self, service):
        """Top-level row: GT string should match single-element pred array."""
        gt_group = [
            {
                "field_name": "forward_looking_estimates_table.hierarchy_path",
                "value": "GAAP additions to property, plant and equipment (gross capital expenditures)"
            },
            {
                "field_name": "forward_looking_estimates_table.period_1_value",
                "value": "$ 25.0"
            }
        ]
        
        pred_row = {
            "instance": 1,
            "fields": {
                "hierarchy_path": ["GAAP additions to property, plant and equipment (gross capital expenditures)"],
                "period_1_value": "$ 25.0"
            }
        }
        
        score = service._calculate_row_match_score(
            gt_group, pred_row, "forward_looking_estimates_table"
        )
        
        assert score > 0.5, f"Expected high match score for top-level row, got {score}"
    
    def test_calculate_row_match_score_no_match_different_leaf(self, service):
        """Should NOT match when GT string doesn't match pred leaf."""
        gt_group = [
            {
                "field_name": "forward_looking_estimates_table.hierarchy_path",
                "value": "Partner contributions, net"  # Different leaf
            },
            {
                "field_name": "forward_looking_estimates_table.period_1_value",
                "value": "(13.0)"
            }
        ]
        
        pred_row = {
            "instance": 2,
            "fields": {
                "hierarchy_path": [
                    "GAAP additions",
                    "Proceeds from capital-related"  # Different from GT
                ],
                "period_1_value": "(1.0)"  # Also different value
            }
        }
        
        score = service._calculate_row_match_score(
            gt_group, pred_row, "forward_looking_estimates_table"
        )
        
        # Should get low/no score since nothing matches
        assert score < 0.5, f"Expected low match score for non-matching row, got {score}"


class TestFallbackExactMatch:
    """Tests for fallback exact matching (when LLM call fails)."""
    
    @pytest.fixture
    def service(self):
        """Create evaluation service with mocked dependencies."""
        with patch('uu_backend.services.evaluation_service.get_extraction_service'), \
             patch('uu_backend.services.evaluation_service.get_document_repository'), \
             patch('uu_backend.services.evaluation_service.get_openai_client'):
            return EvaluationService()
    
    def test_fallback_hierarchy_path_string_vs_array(self, service):
        """Fallback matching should handle string GT vs array pred for hierarchy_path."""
        comparison_schema = {
            "forward_looking_estimates_table.hierarchy_path": {
                "ground_truth": [
                    {"value": "GAAP additions", "instance": 1},
                    {"value": "Proceeds from capital-related", "instance": 2},
                    {"value": "Partner contributions, net", "instance": 3},
                ],
                "predicted": [
                    {"value": ["GAAP additions"], "instance": 1},
                    {"value": ["GAAP additions", "Proceeds from capital-related"], "instance": 2},
                    {"value": ["GAAP additions", "Partner contributions, net"], "instance": 3},
                ]
            }
        }
        
        result = service._fallback_exact_match(comparison_schema)
        
        field_eval = result["forward_looking_estimates_table.hierarchy_path"]
        matches = field_eval["matches"]
        
        # All 3 should match (row 1: exact single, rows 2-3: leaf match)
        assert len(matches) == 3, f"Expected 3 matches, got {len(matches)}"
        
        # No missing or extra
        assert len(field_eval["missing_gt_indices"]) == 0
        assert len(field_eval["extra_pred_indices"]) == 0
    
    def test_fallback_array_gt_vs_array_pred(self, service):
        """Both GT and pred as arrays should match exactly."""
        comparison_schema = {
            "table.hierarchy_path": {
                "ground_truth": [
                    {"value": ["Level 1", "Level 2"], "instance": 1},
                ],
                "predicted": [
                    {"value": ["Level 1", "Level 2"], "instance": 1},
                ]
            }
        }
        
        result = service._fallback_exact_match(comparison_schema)
        field_eval = result["table.hierarchy_path"]
        
        assert len(field_eval["matches"]) == 1
        assert field_eval["matches"][0]["is_match"] is True
    
    def test_fallback_regular_fields_still_work(self, service):
        """Non-hierarchy_path fields should still use exact matching."""
        comparison_schema = {
            "table.period_1_value": {
                "ground_truth": [
                    {"value": "$ 25.0", "instance": 1},
                    {"value": "(1.0)", "instance": 2},
                ],
                "predicted": [
                    {"value": "$ 25.0", "instance": 1},
                    {"value": "(1.0)", "instance": 2},
                ]
            }
        }
        
        result = service._fallback_exact_match(comparison_schema)
        field_eval = result["table.period_1_value"]
        
        assert len(field_eval["matches"]) == 2
        assert len(field_eval["missing_gt_indices"]) == 0


class TestNormalizeValueForComparison:
    """Tests for value normalization."""
    
    @pytest.fixture
    def service(self):
        with patch('uu_backend.services.evaluation_service.get_extraction_service'), \
             patch('uu_backend.services.evaluation_service.get_document_repository'), \
             patch('uu_backend.services.evaluation_service.get_openai_client'):
            return EvaluationService()
    
    def test_normalize_array_to_string(self, service):
        """Arrays should be joined with ' > ' separator."""
        result = service._normalize_value_for_comparison(["Level 1", "Level 2", "Level 3"])
        assert result == "Level 1 > Level 2 > Level 3"
    
    def test_normalize_string_passthrough(self, service):
        """Strings should pass through with strip."""
        result = service._normalize_value_for_comparison("  hello world  ")
        assert result == "hello world"
    
    def test_normalize_none(self, service):
        """None should return empty string."""
        result = service._normalize_value_for_comparison(None)
        assert result == ""


class TestComparisonSchemaBuilding:
    """Tests for building the comparison schema from GT and predictions."""
    
    @pytest.fixture
    def service(self):
        with patch('uu_backend.services.evaluation_service.get_extraction_service'), \
             patch('uu_backend.services.evaluation_service.get_document_repository'), \
             patch('uu_backend.services.evaluation_service.get_openai_client'):
            return EvaluationService()
    
    def test_build_schema_flattens_hierarchy_path_arrays_correctly(self, service):
        """hierarchy_path arrays should remain as atomic values, not be iterated."""
        from uu_backend.models.taxonomy import ExtractedField, ExtractionResult
        from datetime import datetime
        
        # Mock extraction result with hierarchy_path as array
        extraction = MagicMock()
        extraction.fields = [
            ExtractedField(
                field_name="forward_looking_estimates_table",
                value=[
                    {
                        "hierarchy_path": ["GAAP additions", "Proceeds from capital-related"],
                        "period_1_value": "(1.0)"
                    }
                ],
                confidence=0.95,
                source_text=None
            )
        ]
        
        # Ground truth with string hierarchy_path
        ground_truth = [
            {
                "field_name": "forward_looking_estimates_table.hierarchy_path",
                "value": "Proceeds from capital-related",
                "instance_num": 1
            },
            {
                "field_name": "forward_looking_estimates_table.period_1_value",
                "value": "(1.0)",
                "instance_num": 1
            }
        ]
        
        schema = service._build_comparison_schema(ground_truth, extraction)
        
        # Check that hierarchy_path was flattened correctly
        hp_key = "forward_looking_estimates_table.hierarchy_path"
        assert hp_key in schema
        
        # The predicted value should be the array, not individual strings
        pred_values = schema[hp_key]["predicted"]
        assert len(pred_values) == 1
        assert pred_values[0]["value"] == ["GAAP additions", "Proceeds from capital-related"]


class TestEndToEndScenario:
    """End-to-end test mimicking the actual failing scenario."""
    
    @pytest.fixture
    def service(self):
        with patch('uu_backend.services.evaluation_service.get_extraction_service'), \
             patch('uu_backend.services.evaluation_service.get_document_repository'), \
             patch('uu_backend.services.evaluation_service.get_openai_client'):
            return EvaluationService()
    
    def test_forward_looking_estimates_table_matching(self, service):
        """
        Test the exact scenario from the bug report:
        - 8 rows with hierarchy_path
        - GT has string hierarchy_path (leaf nodes)
        - Pred has array hierarchy_path (full paths)
        """
        # This represents what the extraction produces
        predictions = [
            {"hierarchy_path": ["GAAP additions to property, plant and equipment (gross capital expenditures)"], 
             "period_1_value": "$ 25.0", "period_2_value": "$20.0 - $23.0"},
            {"hierarchy_path": ["GAAP additions to property, plant and equipment (gross capital expenditures)", "Proceeds from capital-related government incentives"],
             "period_1_value": "(1.0)", "period_2_value": "(4.0 - 6.0)"},
            {"hierarchy_path": ["GAAP additions to property, plant and equipment (gross capital expenditures)", "Partner contributions, net"],
             "period_1_value": "(13.0)", "period_2_value": "(4.0 - 5.0)"},
            {"hierarchy_path": ["Non-GAAP capital spending"],
             "period_1_value": "$ 11.0", "period_2_value": "$12.0 - $14.0"},
            {"hierarchy_path": ["GAAP R&D and MG&A"],
             "period_1_value": "", "period_2_value": "$ 20.0"},
            {"hierarchy_path": ["GAAP R&D and MG&A", "Acquisition-related adjustments"],
             "period_1_value": "", "period_2_value": "(0.1)"},
            {"hierarchy_path": ["GAAP R&D and MG&A", "Share-based compensation"],
             "period_1_value": "", "period_2_value": "(2.4)"},
            {"hierarchy_path": ["Non-GAAP R&D and MG&A"],
             "period_1_value": "", "period_2_value": "$ 17.5"},
        ]
        
        # This represents what GT labels look like (strings, not arrays)
        gt_labels = [
            # Row 1
            {"field_name": "forward_looking_estimates_table.hierarchy_path", 
             "value": "GAAP additions to property, plant and equipment (gross capital expenditures)", 
             "instance_num": 1},
            {"field_name": "forward_looking_estimates_table.period_1_value", 
             "value": "$ 25.0", "instance_num": 1},
            {"field_name": "forward_looking_estimates_table.period_2_value",
             "value": "$20.0 - $23.0", "instance_num": 1},
            # Row 2
            {"field_name": "forward_looking_estimates_table.hierarchy_path",
             "value": "Proceeds from capital-related government incentives",  # Just the leaf!
             "instance_num": 2},
            {"field_name": "forward_looking_estimates_table.period_1_value",
             "value": "(1.0)", "instance_num": 2},
            {"field_name": "forward_looking_estimates_table.period_2_value",
             "value": "(4.0 - 6.0)", "instance_num": 2},
            # Row 3
            {"field_name": "forward_looking_estimates_table.hierarchy_path",
             "value": "Partner contributions, net",  # Just the leaf!
             "instance_num": 3},
            {"field_name": "forward_looking_estimates_table.period_1_value",
             "value": "(13.0)", "instance_num": 3},
            {"field_name": "forward_looking_estimates_table.period_2_value",
             "value": "(4.0 - 5.0)", "instance_num": 3},
            # Row 4
            {"field_name": "forward_looking_estimates_table.hierarchy_path",
             "value": "Non-GAAP capital spending",
             "instance_num": 4},
            {"field_name": "forward_looking_estimates_table.period_1_value",
             "value": "$ 11.0", "instance_num": 4},
            {"field_name": "forward_looking_estimates_table.period_2_value",
             "value": "$12.0 - $14.0", "instance_num": 4},
        ]
        
        # Build comparison schema
        from uu_backend.models.taxonomy import ExtractedField
        
        extraction = MagicMock()
        extraction.fields = [
            ExtractedField(
                field_name="forward_looking_estimates_table",
                value=predictions,
                confidence=0.95,
                source_text=None
            )
        ]
        
        schema = service._build_comparison_schema(gt_labels, extraction)
        
        # Run fallback matching
        eval_results = service._fallback_exact_match(schema)
        
        # Check hierarchy_path matching
        hp_eval = eval_results.get("forward_looking_estimates_table.hierarchy_path", {})
        matches = hp_eval.get("matches", [])
        
        # All 4 GT hierarchy_paths should match their corresponding predictions
        # Row 1: "GAAP additions..." (string) matches ["GAAP additions..."] (single-elem array)
        # Row 2: "Proceeds..." (string) matches ["GAAP additions...", "Proceeds..."] (leaf match)
        # Row 3: "Partner..." (string) matches ["GAAP additions...", "Partner..."] (leaf match)  
        # Row 4: "Non-GAAP capital spending" (string) matches ["Non-GAAP capital spending"] (exact)
        assert len(matches) >= 4, f"Expected at least 4 hierarchy matches, got {len(matches)}: {matches}"
        
        # No missing GT values
        missing = hp_eval.get("missing_gt_indices", [])
        assert len(missing) == 0, f"Expected no missing GT, got {missing}"


class TestAnnotationSuggestionServiceFlattening:
    """Tests for annotation suggestion service's flattening logic.
    
    The key requirement is that leaf arrays (like hierarchy_path: string[])
    are kept as atomic values, not flattened into separate elements.
    """
    
    @pytest.fixture
    def service(self):
        """Create suggestion service with mocked dependencies."""
        with patch('uu_backend.services.annotation_suggestion_service.get_extraction_service'), \
             patch('uu_backend.services.annotation_suggestion_service.get_azure_di_service'), \
             patch('uu_backend.services.annotation_suggestion_service.get_document_repository'):
            from uu_backend.services.annotation_suggestion_service import AnnotationSuggestionService
            return AnnotationSuggestionService()
    
    def test_flatten_value_keeps_hierarchy_path_atomic(self, service):
        """hierarchy_path arrays should NOT be flattened into separate values."""
        from uu_backend.models.taxonomy import ExtractedField
        
        # Mock extraction with hierarchy_path as array
        fields = [
            ExtractedField(
                field_name="table",
                value=[
                    {
                        "hierarchy_path": ["Level 1", "Level 2"],
                        "amount": "$100"
                    },
                    {
                        "hierarchy_path": ["Level 1", "Level 2", "Level 3"],
                        "amount": "$200"
                    }
                ],
                confidence=0.95,
                source_text=None
            )
        ]
        
        flat_fields = service._flatten_extraction_fields(fields)
        
        # Find hierarchy_path entries
        hp_entries = [(name, val, inst) for name, val, inst in flat_fields if "hierarchy_path" in name]
        
        # Should have 2 hierarchy_path entries (one per row), NOT 5 (one per path element)
        assert len(hp_entries) == 2, f"Expected 2 hierarchy_path entries, got {len(hp_entries)}: {hp_entries}"
        
        # Each entry should have the FULL array, not individual strings
        for name, val, inst in hp_entries:
            assert isinstance(val, list), f"hierarchy_path value should be list, got {type(val)}: {val}"
        
        # Check the values are correct
        values_by_instance = {inst: val for name, val, inst in hp_entries}
        assert values_by_instance[1] == ["Level 1", "Level 2"]
        assert values_by_instance[2] == ["Level 1", "Level 2", "Level 3"]
    
    def test_flatten_value_flattens_row_arrays(self, service):
        """Row arrays (array of objects) should still be flattened into separate instances."""
        from uu_backend.models.taxonomy import ExtractedField
        
        fields = [
            ExtractedField(
                field_name="line_items",
                value=[
                    {"description": "Item A", "quantity": "1"},
                    {"description": "Item B", "quantity": "2"},
                ],
                confidence=0.95,
                source_text=None
            )
        ]
        
        flat_fields = service._flatten_extraction_fields(fields)
        
        # Should have 4 entries: 2 descriptions + 2 quantities
        assert len(flat_fields) == 4
        
        # Check instance numbers are assigned correctly
        descriptions = [(name, val, inst) for name, val, inst in flat_fields if "description" in name]
        assert len(descriptions) == 2
        assert descriptions[0][2] == 1  # Instance 1
        assert descriptions[1][2] == 2  # Instance 2
    
    def test_flatten_value_handles_nested_structure(self, service):
        """Complex nested structures should be handled correctly."""
        from uu_backend.models.taxonomy import ExtractedField
        
        # This mimics the forward_looking_estimates_table structure
        fields = [
            ExtractedField(
                field_name="forward_looking_estimates_table",
                value=[
                    {
                        "hierarchy_path": ["GAAP additions"],
                        "period_1_value": "$ 25.0",
                        "period_2_value": "$20.0 - $23.0"
                    },
                    {
                        "hierarchy_path": ["GAAP additions", "Proceeds from incentives"],
                        "period_1_value": "(1.0)",
                        "period_2_value": "(4.0 - 6.0)"
                    },
                ],
                confidence=0.95,
                source_text=None
            )
        ]
        
        flat_fields = service._flatten_extraction_fields(fields)
        
        # Should have 6 entries: 2 rows × 3 fields per row
        assert len(flat_fields) == 6, f"Expected 6 entries, got {len(flat_fields)}: {flat_fields}"
        
        # hierarchy_path values should be arrays
        hp_entries = [(name, val, inst) for name, val, inst in flat_fields if "hierarchy_path" in name]
        assert len(hp_entries) == 2
        
        # Row 1: single-element path
        row1_hp = next((val for name, val, inst in hp_entries if inst == 1), None)
        assert row1_hp == ["GAAP additions"]
        
        # Row 2: two-element path
        row2_hp = next((val for name, val, inst in hp_entries if inst == 2), None)
        assert row2_hp == ["GAAP additions", "Proceeds from incentives"]


class TestSchemaConsistency:
    """Tests ensuring ground truth and predictions use the same schema format."""
    
    def test_ground_truth_array_values_match_predictions(self):
        """
        When ground truth stores hierarchy_path as an array (new format),
        it should match predictions exactly.
        """
        from uu_backend.services.evaluation_service import EvaluationService
        from uu_backend.models.taxonomy import ExtractedField
        
        with patch('uu_backend.services.evaluation_service.get_extraction_service'), \
             patch('uu_backend.services.evaluation_service.get_document_repository'), \
             patch('uu_backend.services.evaluation_service.get_openai_client'):
            service = EvaluationService()
        
        # Predictions with array hierarchy_path
        predictions = [
            {
                "hierarchy_path": ["GAAP R&D", "Share-based compensation"],
                "period_1_value": "(2.4)"
            }
        ]
        
        # Ground truth ALSO uses array hierarchy_path (new correct format)
        gt_labels = [
            {
                "field_name": "table.hierarchy_path",
                "value": ["GAAP R&D", "Share-based compensation"],  # Array, not string!
                "instance_num": 1
            },
            {
                "field_name": "table.period_1_value",
                "value": "(2.4)",
                "instance_num": 1
            }
        ]
        
        extraction = MagicMock()
        extraction.fields = [
            ExtractedField(
                field_name="table",
                value=predictions,
                confidence=0.95,
                source_text=None
            )
        ]
        
        schema = service._build_comparison_schema(gt_labels, extraction)
        eval_results = service._fallback_exact_match(schema)
        
        # hierarchy_path should match exactly (array == array)
        hp_eval = eval_results.get("table.hierarchy_path", {})
        matches = hp_eval.get("matches", [])
        
        assert len(matches) == 1, f"Expected 1 match, got {len(matches)}"
        assert matches[0]["is_match"] is True
