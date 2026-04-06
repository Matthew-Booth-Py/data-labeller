"""Service for generating AI annotation suggestions."""

import logging
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from uu_backend.config import get_settings
from uu_backend.django_data import models as orm
from uu_backend.models.annotation import AnnotationSuggestion, AnnotationType
from uu_backend.models.taxonomy import DocumentType
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.extraction_service import get_extraction_service

logger = logging.getLogger(__name__)


class AnnotationSuggestionService:
    """Service for generating AI-powered annotation suggestions."""

    def __init__(self):
        self.extraction_service = get_extraction_service()
        self.doc_repo = get_document_repository()

    def suggest_annotations(
        self, document_id: str, document_type: DocumentType
    ) -> list[AnnotationSuggestion]:
        """
        Generate AI annotation suggestions for a document.

        Uses retrieval-vision extraction to get field values and the relevant
        page numbers, then uses pdfplumber on those pages to get word-level
        bounding boxes for positioning the suggestion overlays.
        """
        logger.info(f"Generating annotation suggestions for document {document_id}")

        document = self.doc_repo.get_document(document_id)
        if not document:
            logger.error(f"Document not found: {document_id}")
            return []

        try:
            # extract_auto routes each field through the correct extraction path:
            # retrieval_table fields get their rows parsed deterministically from the
            # retrieved chunk; remaining fields use retrieval-vision LLM extraction.
            # Both paths populate source_page_numbers and field_evidence_regions so
            # pdfplumber can place bbox highlights on the right pages.
            extraction_result = self.extraction_service.extract_auto(
                document_id=document_id
            )

            logger.info(f"Extraction returned {len(extraction_result.fields)} fields")
            logger.info(f"Source pages from extraction: {extraction_result.source_page_numbers}")
            field_region_constraints = self._build_field_region_constraints(
                extraction_result.request_metadata
            )

            # Identify retrieval_table fields using the metadata set by extract_auto.
            # This is more reliable than reading document_type.schema_fields because
            # extract_auto and suggest_annotations may fetch the schema from different
            # sources at different times.
            rt_field_pages: dict = (
                (extraction_result.request_metadata or {}).get("retrieval_table_field_pages", {})
                if isinstance(extraction_result.request_metadata, dict)
                else {}
            )
            retrieval_table_field_names: set[str] = set(rt_field_pages.keys())
            logger.info(
                "retrieval_table fields detected from extraction metadata: %s",
                retrieval_table_field_names,
            )

            suggestions: list[AnnotationSuggestion] = []

            # --- Retrieval-table fields: use citation bbox, no pdfplumber text matching ---
            rt_suggestions = self._create_retrieval_table_suggestions(
                document_id=document_id,
                extraction_result=extraction_result,
                retrieval_table_field_names=retrieval_table_field_names,
                field_region_constraints=field_region_constraints,
            )
            suggestions.extend(rt_suggestions)
            logger.info(
                f"Created {len(rt_suggestions)} retrieval-table bbox suggestion(s) for fields: "
                f"{retrieval_table_field_names}"
            )

            # --- LLM fields: pdfplumber word-level bbox matching ---
            positioned_words = self._get_pdf_words_for_pages(
                document_id=document_id,
                file_type=document.file_type,
                page_numbers=extraction_result.source_page_numbers,
            )
            logger.info(
                f"Got {len(positioned_words)} positioned words on pages "
                f"{extraction_result.source_page_numbers}"
            )

            # Flatten nested extraction results, skipping retrieval_table fields
            flat_fields = self._flatten_extraction_fields(
                [f for f in extraction_result.fields if f.field_name not in retrieval_table_field_names]
            )
            logger.info(f"Flattened to {len(flat_fields)} LLM field values")

            # Track used line indices to avoid matching the same bbox twice
            used_line_indices: set[int] = set()

            for field_name, value, instance_num in flat_fields:
                if value is None or value == "":
                    continue
                # Skip empty arrays
                if isinstance(value, list) and len(value) == 0:
                    continue

                suggestion = self._create_suggestion(
                    document=document,
                    field_name=field_name,
                    value=value,  # Keep original type (string or array)
                    instance_num=instance_num,
                    positioned_words=positioned_words,
                    used_line_indices=used_line_indices,
                    allowed_regions=self._regions_for_field(
                        field_name,
                        field_region_constraints,
                    ),
                )

                if suggestion:
                    suggestions.append(suggestion)
                    logger.debug(f"Created suggestion for {field_name} = '{value}'")
                else:
                    logger.debug(f"Could not create suggestion for {field_name} = '{value}'")

            logger.info(f"Generated {len(suggestions)} suggestions for document {document_id}")
            return suggestions

        except Exception as e:
            logger.error(f"Error generating suggestions for document {document_id}: {e}")
            import traceback

            traceback.print_exc()
            return []

    def suggest_field(
        self, document_id: str, document_type: "DocumentType", field_name: str
    ) -> list["AnnotationSuggestion"]:
        """Run retrieval-based extraction for a single retrieval_table field and return suggestions."""
        from uu_backend.models.taxonomy import ExtractionMethod

        schema_fields = document_type.schema_fields or []
        field = next((f for f in schema_fields if f.name == field_name), None)
        if field is None:
            logger.warning("suggest_field: field '%s' not found in schema", field_name)
            return []

        if getattr(field, "extraction_method", None) != ExtractionMethod.RETRIEVAL_TABLE:
            # For non-retrieval_table array fields, run a targeted retrieval search using
            # the field name as the query and parse the best matching table chunk.
            field.extraction_method = ExtractionMethod.RETRIEVAL_TABLE
            if not getattr(field, "retrieval_query", None):
                field.retrieval_query = field.name.replace("_", " ")

        (
            extracted_fields,
            _source_pages,
            field_evidence_regions,
            field_page_map,
        ) = self.extraction_service._extract_retrieval_table_fields(document_id, [field])

        suggestions: list[AnnotationSuggestion] = []
        for extracted_field in extracted_fields:
            if extracted_field.field_name != field_name:
                continue
            value = extracted_field.value
            if not value:
                continue

            regions = field_evidence_regions.get(field_name, [])
            annotation_data: dict | None = None

            if regions:
                # Convert raw bbox region to percentage coords
                from uu_backend.django_data import models as orm

                r = regions[0]
                bbox = r.get("bbox")
                page_number = r.get("page_number")
                page_id = r.get("page_id")
                if bbox and len(bbox) == 4 and page_number and page_id:
                    page = orm.RetrievalPageModel.objects.filter(id=page_id).first()
                    if page and float(page.width) > 0 and float(page.height) > 0:
                        pw, ph = float(page.width), float(page.height)
                        x0, y0, x1, y1 = [float(v) for v in bbox]
                        annotation_data = {
                            "page": page_number,
                            "x": (x0 / pw) * 100.0,
                            "y": (y0 / ph) * 100.0,
                            "width": ((x1 - x0) / pw) * 100.0,
                            "height": ((y1 - y0) / ph) * 100.0,
                        }

            if annotation_data is None and field_name in field_page_map:
                annotation_data = {
                    "page": field_page_map[field_name],
                    "x": 0.0,
                    "y": 0.0,
                    "width": 100.0,
                    "height": 100.0,
                }

            if annotation_data is None:
                continue

            row_count = len(value) if isinstance(value, list) else 1
            suggestions.append(
                AnnotationSuggestion(
                    id=str(uuid4()),
                    document_id=document_id,
                    field_name=field_name,
                    value=value,
                    annotation_type=AnnotationType.BBOX,
                    annotation_data=annotation_data,
                    confidence=extracted_field.confidence or 0.95,
                    text_snippet=f"{row_count} row{'s' if row_count != 1 else ''}",
                )
            )

        logger.info("suggest_field '%s': generated %d suggestion(s)", field_name, len(suggestions))
        return suggestions

    def _create_retrieval_table_suggestions(
        self,
        document_id: str,
        extraction_result: Any,
        retrieval_table_field_names: set[str],
        field_region_constraints: dict[str, list[dict]],
    ) -> list[AnnotationSuggestion]:
        """Create a single bbox suggestion per retrieval_table field using the table's
        citation region bbox rather than pdfplumber text matching."""
        suggestions = []
        field_page_map: dict[str, int] = (
            (extraction_result.request_metadata or {}).get("retrieval_table_field_pages", {})
            if isinstance(extraction_result.request_metadata, dict)
            else {}
        )

        for extracted_field in extraction_result.fields:
            field_name = extracted_field.field_name
            if field_name not in retrieval_table_field_names:
                continue

            value = extracted_field.value
            if not value:
                logger.info("[RT SUGGEST] field '%s' has no value, skipping", field_name)
                continue

            regions = field_region_constraints.get(field_name, [])
            logger.info(
                "[RT SUGGEST] field '%s': %d row(s), %d constraint region(s), page_map=%s",
                field_name,
                len(value) if isinstance(value, list) else 1,
                len(regions),
                field_page_map.get(field_name),
            )

            # Prefer a citation-derived bbox region; fall back to full page
            annotation_data: dict | None = None
            if regions:
                r = regions[0]
                annotation_data = {
                    "page": r["page"],
                    "x": r["x"],
                    "y": r["y"],
                    "width": r["width"],
                    "height": r["height"],
                }
            elif field_name in field_page_map:
                # No citation bbox available — cover the full page so the annotation
                # still lands on the right page.
                annotation_data = {
                    "page": field_page_map[field_name],
                    "x": 0.0,
                    "y": 0.0,
                    "width": 100.0,
                    "height": 100.0,
                }

            if annotation_data is None:
                logger.warning(
                    "[RETRIEVAL TABLE] No bbox available for field '%s', skipping suggestion",
                    field_name,
                )
                continue

            row_count = len(value) if isinstance(value, list) else 1
            suggestions.append(
                AnnotationSuggestion(
                    id=str(uuid4()),
                    document_id=document_id,
                    field_name=field_name,
                    value=value,
                    annotation_type=AnnotationType.BBOX,
                    annotation_data=annotation_data,
                    confidence=extracted_field.confidence or 0.95,
                    text_snippet=f"{row_count} row{'s' if row_count != 1 else ''}",
                )
            )

        return suggestions

    def _get_pdf_words_for_pages(
        self,
        document_id: str,
        file_type: str,
        page_numbers: list[int],
    ) -> list[dict]:
        """
        Extract word-level text and bounding boxes from selected PDF pages.
        """
        if not page_numbers or file_type.lower() != "pdf":
            return []

        try:
            settings = get_settings()
            file_path = Path(f"{settings.file_storage_path}/{document_id}.{file_type.lower()}")
            if not file_path.exists():
                logger.error(f"PDF file not found: {file_path}")
                return []

            words = self._extract_with_pdfplumber(file_path, page_numbers)
            logger.info(
                f"Using pdfplumber results: {len(words)} words from {len(page_numbers)} pages"
            )
            return words

        except Exception as e:
            logger.error(f"Error extracting text from pages {page_numbers}: {e}", exc_info=True)
            return []

    def _extract_with_pdfplumber(self, file_path: Path, page_numbers: list[int]) -> list[dict]:
        """Extract text + bounding boxes using pdfplumber (for selectable text PDFs).

        Returns word-level bounding boxes (not line-level) for more precise matching.
        """
        import pdfplumber

        all_words = []
        logger.info(f"Trying pdfplumber for {len(page_numbers)} pages: {sorted(set(page_numbers))}")

        with pdfplumber.open(str(file_path)) as pdf:
            total_pages = len(pdf.pages)

            for page_num in sorted(set(page_numbers)):
                zero_idx = page_num - 1
                if not (0 <= zero_idx < total_pages):
                    continue

                page = pdf.pages[zero_idx]
                page_w = float(page.width)
                page_h = float(page.height)

                # Extract words with individual bounding boxes
                words = page.extract_words(x_tolerance=3, y_tolerance=3)

                if not words:
                    continue

                # Keep each word as a separate "line" for precise matching
                for word in words:
                    all_words.append(
                        {
                            "text": word["text"],
                            "page": page_num,
                            "x": (word["x0"] / page_w) * 100,
                            "y": (word["top"] / page_h) * 100,
                            "width": ((word["x1"] - word["x0"]) / page_w) * 100,
                            "height": ((word["bottom"] - word["top"]) / page_h) * 100,
                        }
                    )

        logger.debug(f"pdfplumber extracted {len(all_words)} words from {len(page_numbers)} pages")
        return all_words

    def _flatten_extraction_fields(self, fields: list) -> list[tuple[str, Any, int]]:
        """
        Flatten nested extraction fields into (field_name, value, instance_num) tuples.

        E.g., line_items: [{quantity: 1, description: "foo"}, {quantity: 2}]
        becomes: [("line_items.quantity", "1", 1), ("line_items.description", "foo", 1),
                  ("line_items.quantity", "2", 2)]

        Also handles deeply nested structures like:
        policy_coverages_table[0].limits[0].amount
        """
        result: list[tuple[str, Any, int]] = []

        for field in fields:
            field_name = field.field_name
            value = field.value
            self._flatten_value(field_name, value, 0, result)

        return result

    def _build_field_region_constraints(
        self,
        request_metadata: dict[str, Any] | None,
    ) -> dict[str, list[dict[str, float | int | str | None]]]:
        raw_mapping = (
            (request_metadata or {}).get("field_evidence_regions", {})
            if isinstance(request_metadata, dict)
            else {}
        )
        if not isinstance(raw_mapping, dict):
            return {}

        page_dimensions: dict[str, tuple[float, float]] = {}
        constraints: dict[str, list[dict[str, float | int | str | None]]] = {}

        for field_name, regions in raw_mapping.items():
            if not isinstance(field_name, str) or not isinstance(regions, list):
                continue

            normalized_regions: list[dict[str, float | int | str | None]] = []
            for region in regions:
                if not isinstance(region, dict):
                    continue

                bbox = region.get("bbox")
                page_number = region.get("page_number")
                page_id = region.get("page_id")
                if (
                    not isinstance(bbox, list)
                    or len(bbox) != 4
                    or not isinstance(page_number, int)
                    or not isinstance(page_id, str)
                ):
                    continue

                dimensions = page_dimensions.get(page_id)
                if dimensions is None:
                    page = orm.RetrievalPageModel.objects.filter(id=page_id).first()
                    if page is None:
                        continue
                    dimensions = (float(page.width), float(page.height))
                    page_dimensions[page_id] = dimensions

                page_width, page_height = dimensions
                if page_width <= 0 or page_height <= 0:
                    continue

                x0, y0, x1, y1 = [float(value) for value in bbox]
                normalized_regions.append(
                    {
                        "page": page_number,
                        "x": (x0 / page_width) * 100.0,
                        "y": (y0 / page_height) * 100.0,
                        "width": ((x1 - x0) / page_width) * 100.0,
                        "height": ((y1 - y0) / page_height) * 100.0,
                        "asset_type": region.get("asset_type"),
                        "asset_label": region.get("asset_label"),
                    }
                )

            if normalized_regions:
                constraints[field_name] = normalized_regions

        return constraints

    def _regions_for_field(
        self,
        field_name: str,
        field_region_constraints: dict[str, list[dict[str, float | int | str | None]]],
    ) -> list[dict[str, float | int | str | None]]:
        if field_name in field_region_constraints:
            return field_region_constraints[field_name]

        top_level_field = field_name.split(".", 1)[0]
        return field_region_constraints.get(top_level_field, [])

    def _flatten_value(
        self,
        prefix: str,
        value: Any,
        instance_num: int,
        result: list[tuple[str, Any, int]],
        is_row_item: bool = False,
    ) -> None:
        """
        Recursively flatten a value into field tuples.

        Key distinction:
        - "Row arrays" (array of objects/dicts): Each item is a row, flatten into
          separate instances
        - "Leaf arrays" (array of primitives within a row): Keep as atomic value
          (e.g., hierarchy_path)

        Args:
            prefix: Field name prefix (e.g., "table.field")
            value: The value to flatten
            instance_num: Current instance/row number
            result: Output list of (field_name, value, instance_num) tuples
            is_row_item: True if we're processing fields within a row (changes array handling)
        """
        if value is None or value == "":
            return

        if isinstance(value, list):
            if not value:
                return

            # Check if this is an array of objects (row array) vs array of primitives (leaf array)
            first_item = value[0]
            is_row_array = isinstance(first_item, dict)

            if is_row_array:
                # Array of objects - each item is a row, flatten with instance numbers
                for idx, item in enumerate(value):
                    item_instance = idx + 1
                    for key, val in item.items():
                        # Process row fields with is_row_item=True so nested arrays are kept atomic
                        self._flatten_value(
                            f"{prefix}.{key}", val, item_instance, result, is_row_item=True
                        )
            elif is_row_item:
                # Leaf array within a row (e.g., hierarchy_path: ["Parent", "Child"])
                # Keep as atomic value - this is a single field value, not multiple rows
                result.append((prefix, value, instance_num))
            else:
                # Top-level array of primitives (rare case) - flatten as separate values
                for idx, item in enumerate(value):
                    result.append((prefix, str(item), idx + 1))

        elif isinstance(value, dict):
            # Object - flatten each property
            for key, val in value.items():
                self._flatten_value(
                    f"{prefix}.{key}", val, instance_num, result, is_row_item=is_row_item
                )
        else:
            # Simple value - add to result
            result.append((prefix, str(value), instance_num))

    def _create_suggestion(
        self,
        document: Any,
        field_name: str,
        value: Any,  # Can be string or list (for hierarchy_path etc.)
        instance_num: int,
        positioned_words: list[dict],
        used_line_indices: set[int],
        allowed_regions: list[dict[str, float | int | str | None]] | None = None,
    ) -> AnnotationSuggestion | None:
        """
        Create an annotation suggestion by finding the value in positioned words.

        For array values (like hierarchy_path), uses the LEAF element (last in array)
        to find the bounding box, but stores the FULL array as the annotation value.
        This ensures ground truth matches the extraction schema exactly.
        """
        try:
            # Determine search text and stored value
            # For arrays, search using leaf element but store full array
            if isinstance(value, list):
                if not value:
                    return None
                search_text = str(value[-1])  # Use leaf (last element) for bbox search
                stored_value = value  # Store the full array
                text_snippet = " > ".join(str(v) for v in value)  # Display as path
            else:
                search_text = str(value)
                stored_value = value
                text_snippet = str(value)

            candidate_words = positioned_words
            if field_name.endswith(".hierarchy_path") and allowed_regions:
                candidate_words = self._filter_words_to_metric_column(
                    positioned_words,
                    allowed_regions,
                )

            # Find bounding box for the search text, avoiding already-used lines
            bbox, line_idx = self._find_text_bbox(
                search_text,
                candidate_words,
                used_line_indices,
                allowed_regions=allowed_regions,
            )

            if not bbox:
                logger.debug(f"Could not find bbox for '{search_text}' in field {field_name}")
                return None

            # Mark this line as used so it won't match again
            if line_idx is not None:
                used_line_indices.add(line_idx)

            # Add instance_num to annotation_data
            annotation_data = {**bbox, "instance_num": instance_num} if instance_num > 0 else bbox

            return AnnotationSuggestion(
                id=str(uuid4()),
                document_id=document.id,
                field_name=field_name,
                value=stored_value,  # Store original type (string or array)
                annotation_type=AnnotationType.BBOX,
                annotation_data=annotation_data,
                confidence=0.8,
                text_snippet=text_snippet,
            )

        except Exception as e:
            logger.error(f"Error creating suggestion for field {field_name}: {e}")
            return None

    def _filter_words_to_metric_column(
        self,
        lines: list[dict],
        allowed_regions: list[dict[str, float | int | str | None]],
    ) -> list[dict]:
        filtered_words: list[dict] = []

        for word in lines:
            word_center_x = float(word["x"]) + float(word["width"]) / 2.0
            word_center_y = float(word["y"]) + float(word["height"]) / 2.0

            for region in allowed_regions:
                region_page = region.get("page")
                if region_page is not None and int(region_page) != int(word["page"]):
                    continue

                region_x = float(region.get("x", 0.0) or 0.0)
                region_y = float(region.get("y", 0.0) or 0.0)
                region_width = float(region.get("width", 0.0) or 0.0)
                region_height = float(region.get("height", 0.0) or 0.0)
                metric_region_width = region_width * 0.28

                if (
                    region_x <= word_center_x <= region_x + metric_region_width
                    and region_y <= word_center_y <= region_y + region_height
                ):
                    filtered_words.append(word)
                    break

        return filtered_words or lines

    def _find_text_bbox(
        self,
        search_text: str,
        lines: list[dict],
        used_line_indices: set[int],
        allowed_regions: list[dict[str, float | int | str | None]] | None = None,
    ) -> tuple[dict | None, int | None]:
        """
        Find bounding box for text, supporting both word-level and phrase matching.

        For multi-word search text, finds consecutive words and merges their bounding boxes.
        Skips words/phrases that have already been used to avoid duplicates.

        Returns:
            Tuple of (bbox_dict, line_index) or (None, None) if not found
        """
        if not search_text or not lines:
            return None, None

        search_lower = search_text.lower().strip()
        search_words = search_lower.split()
        search_normalized = self._normalize_text(search_text)

        def make_bbox(word: dict) -> dict:
            return {
                "page": word["page"],
                "x": word["x"],
                "y": word["y"],
                "width": word["width"],
                "height": word["height"],
                "text": word["text"],
            }

        def merge_word_bboxes(word_list: list[dict]) -> dict:
            """Merge multiple word bounding boxes into one."""
            if len(word_list) == 1:
                return make_bbox(word_list[0])

            # All words should be on same page
            page = word_list[0]["page"]

            # Calculate merged bounding box
            min_x = min(w["x"] for w in word_list)
            min_y = min(w["y"] for w in word_list)
            max_x = max(w["x"] + w["width"] for w in word_list)
            max_y = max(w["y"] + w["height"] for w in word_list)

            return {
                "page": page,
                "x": min_x,
                "y": min_y,
                "width": max_x - min_x,
                "height": max_y - min_y,
                "text": " ".join(w["text"] for w in word_list),
            }

        def matches_wrapped_phrase(word_list: list[dict]) -> bool:
            if len(set(word["page"] for word in word_list)) > 1:
                return False

            normalized_sequence = self._normalize_text(
                " ".join(str(word["text"]) for word in word_list)
            )
            if normalized_sequence != search_normalized:
                return False

            min_y = min(float(word["y"]) for word in word_list)
            max_y = max(float(word["y"]) + float(word["height"]) for word in word_list)
            return (max_y - min_y) <= 10.0

        def is_allowed_word(word: dict) -> bool:
            if not allowed_regions:
                return True

            word_center_x = float(word["x"]) + float(word["width"]) / 2.0
            word_center_y = float(word["y"]) + float(word["height"]) / 2.0

            for region in allowed_regions:
                region_page = region.get("page")
                if region_page is not None and int(region_page) != int(word["page"]):
                    continue

                region_x = float(region.get("x", 0.0) or 0.0)
                region_y = float(region.get("y", 0.0) or 0.0)
                region_width = float(region.get("width", 0.0) or 0.0)
                region_height = float(region.get("height", 0.0) or 0.0)
                if (
                    region_x <= word_center_x <= region_x + region_width
                    and region_y <= word_center_y <= region_y + region_height
                ):
                    return True

            return False

        # Strategy 1: Single-word exact match
        if len(search_words) == 1:
            for idx, word in enumerate(lines):
                if idx in used_line_indices:
                    continue
                if not is_allowed_word(word):
                    continue
                if word["text"].lower().strip() == search_lower:
                    return make_bbox(word), idx

        # Strategy 2: Multi-word consecutive match
        if len(search_words) > 1:
            for start_idx in range(len(lines) - len(search_words) + 1):
                if start_idx in used_line_indices:
                    continue

                # Check if consecutive words match
                consecutive_words = lines[start_idx : start_idx + len(search_words)]

                # Skip if any word in sequence is already used
                if any((start_idx + i) in used_line_indices for i in range(len(search_words))):
                    continue
                if not all(is_allowed_word(word) for word in consecutive_words):
                    continue

                # Check if words are on same page and close together (same line)
                if len(set(w["page"] for w in consecutive_words)) > 1:
                    continue

                # Check if y-coordinates are similar (within 5% tolerance for same line)
                y_coords = [w["y"] for w in consecutive_words]
                if max(y_coords) - min(y_coords) > 5:
                    continue

                # Check text match
                consecutive_text = " ".join(w["text"].lower() for w in consecutive_words)
                if consecutive_text == search_lower:
                    return merge_word_bboxes(consecutive_words), start_idx

                if matches_wrapped_phrase(consecutive_words):
                    return merge_word_bboxes(consecutive_words), start_idx

        # Strategy 3: Normalized single-word match
        if len(search_words) == 1:
            for idx, word in enumerate(lines):
                if idx in used_line_indices:
                    continue
                if not is_allowed_word(word):
                    continue
                if self._normalize_text(word["text"]) == search_normalized:
                    return make_bbox(word), idx

        # Strategy 4: Partial match for short search text (fallback)
        for idx, word in enumerate(lines):
            if idx in used_line_indices:
                continue
            if not is_allowed_word(word):
                continue
            if search_lower in word["text"].lower():
                return make_bbox(word), idx

        return None, None

    def extract_table_from_region(
        self,
        document_id: str,
        field_name: str,
        page: int,
        x: float,
        y: float,
        width: float,
        height: float,
        schema_subfields: list[dict] | None = None,
    ) -> list[AnnotationSuggestion]:
        """Extract table data from a specific bbox region drawn by the user.

        Uses pdfplumber to pull text from the cropped region, sends it to the
        LLM structured as a prompt with the sub-field schema, then maps each
        extracted cell value back to a per-word bbox for the suggestion overlay.
        """
        import pdfplumber

        settings = get_settings()
        doc_repo = get_document_repository()
        document = doc_repo.get_document(document_id)

        if not document:
            logger.error("Document not found: %s", document_id)
            return []

        if document.file_type.lower() != "pdf":
            logger.warning("extract_table_from_region only supports PDF, got %s", document.file_type)
            return []

        file_path = Path(f"{settings.file_storage_path}/{document_id}.{document.file_type.lower()}")
        if not file_path.exists():
            logger.error("PDF not found at %s", file_path)
            return []

        try:
            with pdfplumber.open(str(file_path)) as pdf:
                zero_idx = page - 1
                if not (0 <= zero_idx < len(pdf.pages)):
                    logger.error("Page %d out of range (doc has %d pages)", page, len(pdf.pages))
                    return []

                page_obj = pdf.pages[zero_idx]
                page_w = float(page_obj.width)
                page_h = float(page_obj.height)

                # Convert percentage bbox to pdfplumber coords (x0, top, x1, bottom)
                x0 = (x / 100.0) * page_w
                top = (y / 100.0) * page_h
                x1 = ((x + width) / 100.0) * page_w
                bottom = ((y + height) / 100.0) * page_h

                cropped = page_obj.within_bbox((x0, top, x1, bottom))

                # Build word-level bboxes for precise cell matching later
                raw_words = cropped.extract_words(x_tolerance=3, y_tolerance=3)

                # Try pdfplumber's table parser first; fall back to word grouping
                table_grid = cropped.extract_table(
                    table_settings={
                        "vertical_strategy": "lines_strict",
                        "horizontal_strategy": "lines_strict",
                        "snap_tolerance": 3,
                        "join_tolerance": 3,
                    }
                )
                if not table_grid:
                    table_grid = cropped.extract_table(
                        table_settings={
                            "vertical_strategy": "text",
                            "horizontal_strategy": "text",
                            "snap_tolerance": 6,
                        }
                    )

            # Positioned words in percentage-of-page coords for bbox matching
            positioned_words = [
                {
                    "text": w["text"],
                    "page": page,
                    "x": (w["x0"] / page_w) * 100,
                    "y": (w["top"] / page_h) * 100,
                    "width": ((w["x1"] - w["x0"]) / page_w) * 100,
                    "height": ((w["bottom"] - w["top"]) / page_h) * 100,
                }
                for w in raw_words
            ]

            table_text = self._format_table_grid(table_grid) if table_grid else self._words_to_lines(positioned_words)

            if not table_text.strip():
                logger.warning("No text extracted from region for %s", field_name)
                return []

            logger.info("[REGION EXTRACT] Extracted %d chars from region of '%s'", len(table_text), field_name)

            rows = self._llm_extract_table(table_text, field_name, schema_subfields or [])
            if not rows:
                logger.warning("[REGION EXTRACT] LLM returned no rows for '%s'", field_name)
                return []

            logger.info("[REGION EXTRACT] LLM returned %d rows for '%s'", len(rows), field_name)

            region_bounds = [{"page": page, "x": x, "y": y, "width": width, "height": height}]
            suggestions: list[AnnotationSuggestion] = []
            used_line_indices: set[int] = set()

            for instance_num, row in enumerate(rows, start=1):
                if not isinstance(row, dict):
                    continue
                for sub_field, value in row.items():
                    if value is None or str(value).strip() in ("", "None", "null"):
                        continue
                    full_field = f"{field_name}.{sub_field}"
                    value_str = str(value).strip()

                    bbox, line_idx = self._find_text_bbox(
                        value_str,
                        positioned_words,
                        used_line_indices,
                        allowed_regions=region_bounds,
                    )
                    if line_idx is not None:
                        used_line_indices.add(line_idx)

                    if bbox:
                        annotation_data = {**bbox, "instance_num": instance_num}
                    else:
                        # Place approximately within the drawn region
                        row_height_pct = height / max(len(rows), 1)
                        annotation_data = {
                            "page": page,
                            "x": x,
                            "y": y + (instance_num - 1) * row_height_pct,
                            "width": width,
                            "height": row_height_pct,
                            "instance_num": instance_num,
                        }

                    suggestions.append(
                        AnnotationSuggestion(
                            id=str(uuid4()),
                            document_id=document_id,
                            field_name=full_field,
                            value=value_str,
                            annotation_type=AnnotationType.BBOX,
                            annotation_data=annotation_data,
                            confidence=0.85,
                            text_snippet=value_str,
                        )
                    )

            logger.info(
                "[REGION EXTRACT] Created %d suggestions for '%s'", len(suggestions), field_name
            )
            return suggestions

        except Exception as e:
            logger.error("extract_table_from_region failed for %s: %s", document_id, e, exc_info=True)
            return []

    # ------------------------------------------------------------------
    # Private helpers for region extraction
    # ------------------------------------------------------------------

    def _format_table_grid(self, table_grid: list[list[str | None]]) -> str:
        """Format pdfplumber table grid as tab-separated text for the LLM."""
        lines = []
        for row in table_grid:
            cells = [str(c).strip() if c is not None else "" for c in row]
            lines.append("\t".join(cells))
        return "\n".join(lines)

    def _words_to_lines(self, words: list[dict]) -> str:
        """Group positioned words into approximate text lines."""
        if not words:
            return ""
        by_y: dict[int, list[dict]] = {}
        for word in words:
            bucket = round(float(word["y"]))
            by_y.setdefault(bucket, []).append(word)
        lines = []
        for y_bucket in sorted(by_y):
            row_words = sorted(by_y[y_bucket], key=lambda w: float(w["x"]))
            lines.append("  ".join(w["text"] for w in row_words))
        return "\n".join(lines)

    def _llm_extract_table(
        self,
        table_text: str,
        field_name: str,
        schema_subfields: list[dict],
    ) -> list[dict]:
        """Call the LLM to extract structured rows from raw table text."""
        from uu_backend.llm.openai_client import get_openai_client

        if schema_subfields:
            field_list = "\n".join(
                f'  - "{sf["name"]}": {sf.get("description") or sf["name"]}'
                for sf in schema_subfields
            )
            schema_block = (
                f'Extract each row into an object with these exact keys:\n{field_list}'
            )
        else:
            schema_block = (
                "Use the first row as column headers (keys) and extract the remaining rows as data."
            )

        prompt = f"""You are a precise document table extractor.

{schema_block}

TABLE TEXT (tab or space separated):
{table_text}

Rules:
- Return a JSON object with a single key "rows" containing an array of objects.
- Each object is one DATA row (skip pure header rows).
- Use null for blank cells.
- Keep values exactly as they appear in the table — do NOT reformat numbers or dates.
- The field name being extracted is "{field_name}".
"""
        try:
            result = get_openai_client().complete_json(prompt, max_completion_tokens=8000)
            rows = result.get("rows", [])
            return rows if isinstance(rows, list) else []
        except Exception as e:
            logger.error("[REGION EXTRACT] LLM call failed: %s", e)
            return []

    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison (remove punctuation, lowercase)."""
        return re.sub(r"[^\w]", "", text.lower())


# Singleton instance
_suggestion_service: AnnotationSuggestionService | None = None


def get_annotation_suggestion_service() -> AnnotationSuggestionService:
    """Get or create annotation suggestion service singleton."""
    global _suggestion_service
    if _suggestion_service is None:
        _suggestion_service = AnnotationSuggestionService()
    return _suggestion_service
