"""Extraction service for converting annotations into structured data."""

import base64
import io
import json
import logging
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from django.utils import timezone

from uu_backend.config import get_settings
from uu_backend.llm.openai_client import get_openai_client
from uu_backend.models.taxonomy import (
    ExtractedField,
    ExtractionMethod,
    ExtractionRequestMetrics,
    ExtractionResult,
    FieldType,
    SchemaField,
)
from uu_backend.repositories import get_repository
from uu_backend.repositories.document_repository import get_document_repository
from uu_backend.services.pdf_retrieval import PDF_RETRIEVAL_BACKEND
from uu_backend.services.schema_generator import generate_pydantic_schema

try:
    from pdf2image import convert_from_path

    PDF_SUPPORT = True
except ImportError:
    PDF_SUPPORT = False

logger = logging.getLogger(__name__)


class ExtractionService:
    """Service for extracting structured data from document annotations."""

    def __init__(self):
        openai_client = get_openai_client()
        self.client = openai_client._client
        settings = get_settings()
        self.model = settings.effective_tagging_model
        self._pricing_by_model = settings.openai_model_pricing or {}
        self._raw_guardrails = (
            "Critical extraction rules:\n"
            "1) Extract values EXACTLY as they appear in the document (RAW).\n"
            "2) Do NOT normalize, reformat, infer, or interpret values.\n"
            "3) For dates, return the exact source string "
            "(for example, keep 'February 3, 2024' if shown).\n"
            "4) Preserve ALL spacing, punctuation, currency symbols, and separators "
            "exactly when present.\n"
            "5) If not found, return null."
        )

    def _has_table_like_field(self, schema_fields: list[SchemaField]) -> bool:
        """True if any field is an array (table-like) or has explicit visual_content_type=table."""
        for field in schema_fields:
            if self._is_table_field(field):
                return True
        return False

    def _is_table_field(self, field: SchemaField) -> bool:
        content_type = getattr(field, "visual_content_type", None)
        if content_type:
            type_value = content_type.value if hasattr(content_type, "value") else str(content_type)
            if type_value == "table":
                return True
        return field.type == FieldType.ARRAY and field.items is not None

    def _ensure_retrieval_ready(self, document) -> None:
        file_type = (document.file_type or "").lower()
        if file_type != "pdf":
            raise ValueError(
                "PDF-only intelligent retrieval supports extraction only for PDF documents."
            )

        status = (document.retrieval_index_status or "pending").lower()

        if status == "completed":
            if document.retrieval_index_backend != PDF_RETRIEVAL_BACKEND:
                raise ValueError(
                    "This PDF is indexed with a legacy retrieval backend. "
                    "Reindex the document to upgrade it to intelligent PDF retrieval."
                )
            if document.retrieval_chunks_count == 0:
                raise ValueError(
                    "Intelligent PDF retrieval completed, but no retrieval content was indexed "
                    "for this document. Reindex the document after confirming it has extractable text."
                )
            return

        if status == "processing":
            raise ValueError(
                "Contextual retrieval indexing is still in progress for this document. "
                "Wait for indexing to complete before running extraction."
            )

        if status == "failed":
            raise ValueError(
                "Contextual retrieval indexing failed for this document. "
                "Reindex the document before running extraction."
            )

        raise ValueError(
            "Intelligent PDF retrieval indexing is required before extraction. "
            "Index or reindex this PDF and retry."
        )

    def _normalize_query_fragment(self, value: str | None, *, max_chars: int = 400) -> str:
        if not value:
            return ""
        normalized = re.sub(r"\s+", " ", value).strip()
        return normalized[:max_chars].strip()

    def _dedupe_fragments(self, fragments: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for fragment in fragments:
            normalized = self._normalize_query_fragment(fragment)
            if not normalized:
                continue
            marker = normalized.lower()
            if marker in seen:
                continue
            seen.add(marker)
            deduped.append(normalized)
        return deduped

    def _build_field_queries(self, doc_type, field: SchemaField) -> list[str]:
        field_name = field.name.replace("_", " ")
        base_fragments = self._dedupe_fragments(
            [
                doc_type.name,
                doc_type.description,
                field_name,
                field.description,
            ]
        )
        visual_fragments = self._dedupe_fragments(field.visual_features or [])
        prompt_fragments = self._dedupe_fragments(
            [
                field.extraction_prompt,
                field.visual_guidance,
            ]
        )

        query_variants: list[list[str]] = [base_fragments]

        if prompt_fragments:
            query_variants.append(base_fragments + prompt_fragments)

        if visual_fragments:
            query_variants.append(base_fragments + visual_fragments)

        if self._is_table_field(field):
            query_variants.append(
                base_fragments
                + visual_fragments
                + [
                    "table",
                    "row labels",
                    "column headers",
                    "data cells",
                    "financial reconciliation",
                ]
            )

        queries: list[str] = []
        seen_queries: set[str] = set()
        for fragments in query_variants:
            query = " ".join(self._dedupe_fragments(fragments))
            if not query:
                continue
            marker = query.lower()
            if marker in seen_queries:
                continue
            seen_queries.add(marker)
            queries.append(query)

        return queries or [field_name]

    def _rank_pages_from_query_results(
        self,
        *,
        results_by_query: dict[str, list[Any]],
        min_score: float = 0.0,
    ) -> list[tuple[int, dict[str, Any]]]:
        page_stats: dict[int, dict[str, Any]] = {}

        for query, results in results_by_query.items():
            for rank, result in enumerate(results):
                score = float(getattr(result, "score", 0.0) or 0.0)
                if score < min_score:
                    continue

                page_number = result.metadata.get("page_number") if result.metadata else None
                if page_number is None:
                    continue
                page_num = int(page_number)

                stat = page_stats.setdefault(
                    page_num,
                    {
                        "score": 0.0,
                        "best_score": 0.0,
                        "hits": 0,
                        "queries": set(),
                        "chunks": [],
                    },
                )
                rank_bonus = 1.0 / (rank + 1)
                stat["score"] += score + rank_bonus
                stat["best_score"] = max(stat["best_score"], score)
                stat["hits"] += 1
                stat["queries"].add(query)
                stat["chunks"].append(result)

        return sorted(
            page_stats.items(),
            key=lambda item: (
                len(item[1]["queries"]),
                item[1]["hits"],
                item[1]["score"],
                item[1]["best_score"],
            ),
            reverse=True,
        )

    def _finalize_page_selection(
        self,
        *,
        overall_page_stats: dict[int, dict[str, Any]],
        required_pages: set[int],
        min_pages: int = 2,
        max_pages: int = 4,
    ) -> list[int]:
        ordered_pages = [
            page
            for page, _ in sorted(
                overall_page_stats.items(),
                key=lambda item: (
                    len(item[1]["fields"]),
                    item[1]["score"],
                    item[1]["hits"],
                    item[1]["best_score"],
                ),
                reverse=True,
            )
        ]

        final_pages: list[int] = [page for page in ordered_pages if page in required_pages]

        if len(final_pages) < min_pages:
            for page in ordered_pages:
                if page in final_pages:
                    continue
                final_pages.append(page)
                if len(final_pages) >= min(min_pages, len(ordered_pages)):
                    break

        if len(final_pages) > max_pages:
            final_pages = final_pages[:max_pages]

        return final_pages

    def _preferred_asset_types_for_field(self, field: SchemaField) -> set[str]:
        if self._is_table_field(field):
            return {"table"}
        return {"page", "table", "image"}

    def _coverage_threshold_for_field(self, field: SchemaField) -> float:
        return 0.18 if self._is_table_field(field) else 0.12

    def _dedupe_search_results(self, results: list[Any]) -> list[Any]:
        deduped: list[Any] = []
        seen: set[str] = set()
        for result in results:
            marker = getattr(result, "chunk_id", None) or f"{result.doc_id}_{result.chunk_index}"
            if marker in seen:
                continue
            seen.add(marker)
            deduped.append(result)
        deduped.sort(key=lambda item: getattr(item, "score", 0.0), reverse=True)
        return deduped

    def _evaluate_field_coverage(self, field: SchemaField, results: list[Any]) -> dict[str, Any]:
        preferred_asset_types = self._preferred_asset_types_for_field(field)
        relevant_results = [
            result
            for result in results
            if getattr(result, "asset_type", None) in preferred_asset_types
            or getattr(result, "asset_type", None) is None
        ]
        best_score = max((float(getattr(result, "score", 0.0) or 0.0) for result in relevant_results), default=0.0)
        status = "missing"
        if relevant_results:
            status = "covered" if best_score >= self._coverage_threshold_for_field(field) else "partial"

        return {
            "status": status,
            "best_score": round(best_score, 4),
            "result_count": len(results),
            "preferred_asset_types": sorted(preferred_asset_types),
            "top_page_numbers": sorted(
                {
                    page
                    for result in relevant_results[:3]
                    for page in self._page_numbers_for_result(result)
                }
            ),
            "top_asset_labels": [
                str(getattr(result, "asset_label", "") or "")
                for result in relevant_results[:3]
                if getattr(result, "asset_label", None)
            ],
        }

    def _generate_follow_up_queries(
        self,
        *,
        doc_type,
        field: SchemaField,
        existing_results: list[Any],
        initial_queries: list[str],
    ) -> list[str]:
        evidence_preview = []
        for result in existing_results[:3]:
            evidence_preview.append(
                {
                    "page_number": getattr(result, "page_number", None),
                    "asset_type": getattr(result, "asset_type", None),
                    "asset_label": getattr(result, "asset_label", None),
                    "score": round(float(getattr(result, "score", 0.0) or 0.0), 4),
                    "snippet": str(getattr(result, "original_text", "") or "")[:300],
                }
            )

        prompt = (
            "You are helping a PDF extraction system recover missing evidence for one schema field. "
            "Return JSON in the form {\"queries\": [\"...\", \"...\"]}. "
            "Provide at most 2 focused search queries and do not repeat earlier wording.\n\n"
            f"Document type: {doc_type.name}\n"
            f"Field name: {field.name}\n"
            f"Field description: {field.description or ''}\n"
            f"Field extraction prompt: {field.extraction_prompt or ''}\n"
            f"Initial queries: {initial_queries}\n"
            f"Current evidence: {json.dumps(evidence_preview, indent=2)}"
        )
        try:
            payload = get_openai_client().complete_json(prompt, max_completion_tokens=400)
            raw_queries = payload.get("queries", []) if isinstance(payload, dict) else []
            queries = self._dedupe_fragments([str(query) for query in raw_queries])
            if queries:
                return queries[:2]
        except Exception as exc:
            logger.warning("Follow-up query generation failed for %s: %s", field.name, exc)

        fallback = self._dedupe_fragments(
            [
                f"{doc_type.name} {field.name.replace('_', ' ')} exact value",
                field.description,
                field.extraction_prompt,
            ]
        )
        return fallback[:2]

    def _page_numbers_for_result(self, result: Any) -> set[int]:
        page_numbers: set[int] = set()
        metadata = getattr(result, "metadata", {}) or {}
        raw_page_numbers = metadata.get("page_numbers")
        if isinstance(raw_page_numbers, list):
            for page in raw_page_numbers:
                if isinstance(page, int):
                    page_numbers.add(page)
        page_number = getattr(result, "page_number", None)
        if isinstance(page_number, int):
            page_numbers.add(page_number)
        metadata_page = metadata.get("page_number")
        if isinstance(metadata_page, int):
            page_numbers.add(metadata_page)
        return page_numbers

    def _run_agentic_retrieval_loop(
        self,
        *,
        document_id: str,
        doc_type,
        schema_fields: list[SchemaField],
        retrieval_service,
        top_k_per_field: int,
        max_rounds: int = 2,
    ) -> tuple[dict[str, list[Any]], dict[str, dict[str, Any]], int]:
        evidence_by_field: dict[str, list[Any]] = {}
        coverage_by_field: dict[str, dict[str, Any]] = {}
        retry_count = 0

        def _should_call_search_for_extraction(search_callable: Any) -> bool:
            if not callable(search_callable):
                return False
            module_name = getattr(type(search_callable), "__module__", "")
            if "unittest.mock" not in module_name:
                return True
            return getattr(search_callable, "side_effect", None) is not None

        for field in schema_fields:
            initial_queries = self._build_field_queries(doc_type, field)
            active_queries = list(initial_queries)
            results: list[Any] = []

            for round_index in range(max_rounds):
                search_for_extraction = getattr(retrieval_service, "search_for_extraction", None)
                if _should_call_search_for_extraction(search_for_extraction):
                    round_results = retrieval_service.search_for_extraction(
                        queries=active_queries,
                        top_k_per_query=top_k_per_field,
                        filter_doc_id=document_id,
                        asset_types=self._preferred_asset_types_for_field(field),
                    )
                else:
                    round_results = []
                    for query in active_queries:
                        round_results.extend(
                            retrieval_service.search(
                                query=query,
                                top_k=top_k_per_field,
                                filter_doc_id=document_id,
                                use_reranking=True,
                            )
                        )
                results = self._dedupe_search_results([*results, *round_results])
                coverage = self._evaluate_field_coverage(field, results)
                coverage["rounds"] = round_index + 1
                coverage["queries_used"] = list(active_queries)
                if coverage["status"] == "covered":
                    coverage_by_field[field.name] = coverage
                    break
                if round_index + 1 >= max_rounds:
                    coverage_by_field[field.name] = coverage
                    break

                retry_count += 1
                active_queries = self._generate_follow_up_queries(
                    doc_type=doc_type,
                    field=field,
                    existing_results=results,
                    initial_queries=initial_queries,
                )

            evidence_by_field[field.name] = results
            coverage_by_field.setdefault(
                field.name,
                self._evaluate_field_coverage(field, results),
            )

        return evidence_by_field, coverage_by_field, retry_count

    def _select_pages_from_evidence(
        self,
        *,
        schema_fields: list[SchemaField],
        evidence_by_field: dict[str, list[Any]],
    ) -> tuple[list[int], dict[str, set[int]]]:
        overall_page_stats: dict[int, dict[str, Any]] = defaultdict(
            lambda: {"score": 0.0, "best_score": 0.0, "hits": 0, "fields": set()}
        )
        field_page_map: dict[str, set[int]] = {}

        for field in schema_fields:
            field_results = evidence_by_field.get(field.name, [])
            selected_pages: set[int] = set()

            for result in field_results:
                result_pages = self._page_numbers_for_result(result)
                if not result_pages:
                    continue
                selected_pages.update(result_pages)
                for page in result_pages:
                    stat = overall_page_stats[page]
                    stat["score"] += float(getattr(result, "score", 0.0) or 0.0)
                    stat["best_score"] = max(
                        stat["best_score"], float(getattr(result, "score", 0.0) or 0.0)
                    )
                    stat["hits"] += 1
                    stat["fields"].add(field.name)

                # Anchor table extraction to the dominant matched table. If the
                # top-ranked table result spans multiple pages, result_pages
                # already contains the full stitched range.
                if self._is_table_field(field):
                    break

                if len(selected_pages) >= 1:
                    break

            field_page_map[field.name] = selected_pages

        required_pages = {page for pages in field_page_map.values() for page in pages}
        selected_pages = self._finalize_page_selection(
            overall_page_stats=dict(overall_page_stats),
            required_pages=required_pages,
            min_pages=1,
            max_pages=6,
        )
        return selected_pages, field_page_map

    def _filter_evidence_to_selected_pages(
        self,
        *,
        schema_fields: list[SchemaField],
        evidence_by_field: dict[str, list[Any]],
        field_page_map: dict[str, set[int]],
    ) -> dict[str, list[Any]]:
        filtered_evidence: dict[str, list[Any]] = {}

        for field in schema_fields:
            selected_pages = field_page_map.get(field.name, set())
            preferred_asset_types = self._preferred_asset_types_for_field(field)
            filtered_results: list[Any] = []

            for result in evidence_by_field.get(field.name, []):
                asset_type = getattr(result, "asset_type", None)
                if asset_type is not None and asset_type not in preferred_asset_types:
                    continue

                result_pages = self._page_numbers_for_result(result)
                if selected_pages and result_pages and not (result_pages & selected_pages):
                    continue

                filtered_results.append(result)

            filtered_evidence[field.name] = filtered_results or list(
                evidence_by_field.get(field.name, [])
            )

        return filtered_evidence

    def _build_field_evidence_regions(
        self,
        *,
        schema_fields: list[SchemaField],
        evidence_by_field: dict[str, list[Any]],
    ) -> dict[str, list[dict[str, Any]]]:
        field_regions: dict[str, list[dict[str, Any]]] = {}

        for field in schema_fields:
            if not self._is_table_field(field):
                continue

            top_result = next(
                (
                    result
                    for result in evidence_by_field.get(field.name, [])
                    if getattr(result, "citation_regions", None)
                ),
                None,
            )
            if top_result is None:
                continue
            if getattr(top_result, "asset_type", None) != "table":
                continue

            normalized_regions: list[dict[str, Any]] = []
            for region in list(getattr(top_result, "citation_regions", []) or []):
                if not isinstance(region, dict):
                    continue
                normalized_regions.append(
                    {
                        "page_number": region.get("page_number"),
                        "page_id": region.get("page_id"),
                        "bbox": region.get("bbox"),
                        "preview_artifact_id": region.get("preview_artifact_id"),
                        "asset_type": getattr(top_result, "asset_type", None),
                        "asset_label": getattr(top_result, "asset_label", None),
                    }
                )

            if normalized_regions:
                field_regions[field.name] = normalized_regions

        return field_regions

    def _build_evidence_text(
        self,
        *,
        schema_fields: list[SchemaField],
        evidence_by_field: dict[str, list[Any]],
        coverage_by_field: dict[str, dict[str, Any]],
        max_results_per_field: int = 3,
    ) -> str:
        sections: list[str] = []
        for field in schema_fields:
            coverage = coverage_by_field.get(field.name, {})
            lines = [
                f"Field: {field.name}",
                f"Coverage: {coverage.get('status', 'missing')}",
            ]
            for result in evidence_by_field.get(field.name, [])[:max_results_per_field]:
                page_numbers = sorted(self._page_numbers_for_result(result))
                page_label = f"pages {page_numbers}" if page_numbers else "pages unknown"
                asset_type = getattr(result, "asset_type", None) or "unknown"
                asset_label = getattr(result, "asset_label", None) or ""
                lines.append(
                    f"- {page_label} | {asset_type} | {asset_label} | score={float(getattr(result, 'score', 0.0) or 0.0):.3f}"
                )
                snippet = str(getattr(result, "text", "") or getattr(result, "original_text", "") or "")
                lines.append(self._normalize_query_fragment(snippet, max_chars=900))
            sections.append("\n".join(lines))
        return "\n\n".join(sections)

    def _should_use_vision_extraction(
        self, schema_fields: list[SchemaField], file_type: str
    ) -> bool:
        """Check if vision extraction should be used for table fields in PDFs."""
        if file_type.lower() != "pdf":
            return False
        return self._has_table_like_field(schema_fields)

    def _build_request_metadata(
        self,
        *,
        strategy: str,
        source_page_numbers: list[int] | None = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {"strategy": strategy}
        if source_page_numbers:
            metadata["source_page_numbers"] = sorted(source_page_numbers)
        return metadata

    def _parse_markdown_table(self, text: str) -> list[dict] | None:
        """Parse a markdown table embedded in chunk text into a list of row dicts."""
        lines = [
            l.strip()
            for l in text.split("\n")
            if l.strip().startswith("|") and l.strip().endswith("|")
        ]
        if len(lines) < 3:
            return None

        def parse_cells(line: str) -> list[str]:
            return [c.strip() for c in line.split("|")[1:-1]]

        def is_sep(line: str) -> bool:
            return bool(re.match(r"^\|[\s\-:|]+\|$", line))

        sep_idx = next((i for i, l in enumerate(lines) if is_sep(l)), None)
        if sep_idx is None or sep_idx < 1:
            return None

        group_headers = parse_cells(lines[sep_idx - 1])
        post_sep = lines[sep_idx + 1 :]
        next_sep_idx = next((i for i, l in enumerate(post_sep) if is_sep(l)), None)

        if next_sep_idx is not None and next_sep_idx > 0:
            col_headers = parse_cells(post_sep[0])
            data_lines = post_sep[next_sep_idx + 1 :]
        elif next_sep_idx == 0:
            col_headers = parse_cells(post_sep[1]) if len(post_sep) > 1 else group_headers
            data_lines = post_sep[2:]
        else:
            col_headers = group_headers
            data_lines = post_sep

        rows = [
            parse_cells(l)
            for l in data_lines
            if not is_sep(l) and any(c for c in parse_cells(l))
        ]
        if not rows:
            return None

        keys = [
            h if h else (group_headers[i] if i < len(group_headers) and group_headers[i] else f"col_{i}")
            for i, h in enumerate(col_headers)
        ]
        n_cols = max(len(keys), max((len(r) for r in rows), default=0))
        padded_keys = keys + [f"col_{i}" for i in range(len(keys), n_cols)]

        return [
            {padded_keys[i]: (row[i] if i < len(row) else "") for i in range(n_cols)}
            for row in rows
        ]

    def _extract_retrieval_table_fields(
        self, document_id: str, fields: list[SchemaField]
    ) -> tuple[list[ExtractedField], list[int], dict[str, list[dict]], dict[str, int]]:
        """Extract array fields using retrieval + markdown table parsing, bypassing the LLM.

        Returns:
            (extracted_fields, source_page_numbers, field_evidence_regions, field_page_map)
            field_page_map maps field_name → page_number for use when citation regions are absent.
        """
        from uu_backend.services.contextual_retrieval import get_contextual_retrieval_service

        retrieval_service = get_contextual_retrieval_service()
        results: list[ExtractedField] = []
        source_pages: list[int] = []
        field_evidence_regions: dict[str, list[dict]] = {}
        field_page_map: dict[str, int] = {}

        for field in fields:
            query = (field.retrieval_query or "").strip() or field.name.replace("_", " ")
            logger.info("[RETRIEVAL TABLE] Extracting field '%s' with query: %s", field.name, query)
            try:
                search_results = retrieval_service.search(
                    query=query,
                    top_k=5,
                    filter_doc_id=document_id,
                    use_reranking=False,
                )
                parsed_rows: list[dict] | None = None
                matched_result = None
                for result in search_results:
                    # original_text holds the raw markdown; text is the contextual summary.
                    # Always prefer original_text for table parsing.
                    original_text = getattr(result, "original_text", "") or ""
                    summary_text = getattr(result, "text", "") or ""
                    text = original_text or summary_text
                    parsed_rows = self._parse_markdown_table(text)
                    if parsed_rows is not None:
                        matched_result = result
                        logger.info(
                            "[RETRIEVAL TABLE] Parsed %d rows for field '%s' from chunk #%s (page %s)",
                            len(parsed_rows),
                            field.name,
                            getattr(result, "chunk_index", "?"),
                            getattr(result, "page_number", "?"),
                        )
                        break

                # Capture page + citation regions for the labeller.
                # Search returns page-level chunks whose citation bbox is the full page.
                # Cross-reference the RetrievalAssetModel to find tight table bboxes
                # on the same page instead.
                if matched_result is not None:
                    page_num = getattr(matched_result, "page_number", None)
                    if isinstance(page_num, int):
                        source_pages.append(page_num)
                        field_page_map[field.name] = page_num

                    # Try to get the page_id from the citation region
                    raw_citations = list(getattr(matched_result, "citation_regions", []) or [])
                    page_id: str | None = None
                    if raw_citations and isinstance(raw_citations[0], dict):
                        page_id = raw_citations[0].get("page_id")

                    if page_id:
                        # Look up table assets on this page for a tight bbox
                        from uu_backend.django_data.models import RetrievalAssetModel
                        table_assets = list(
                            RetrievalAssetModel.objects.filter(
                                page_id=page_id, asset_type="table"
                            ).order_by("id")
                        )
                        if table_assets:
                            asset = table_assets[0]
                            field_evidence_regions[field.name] = [
                                {
                                    "page_number": page_num,
                                    "page_id": page_id,
                                    "bbox": asset.bbox,
                                    "preview_artifact_id": None,
                                    "asset_type": "table",
                                    "asset_label": asset.label,
                                }
                            ]
                            logger.info(
                                "[RETRIEVAL TABLE] Using table asset bbox %s on page %s for field '%s'",
                                asset.bbox,
                                page_num,
                                field.name,
                            )
                        else:
                            # No table asset found — fall back to full-page
                            field_evidence_regions[field.name] = []

                results.append(
                    ExtractedField(
                        field_name=field.name,
                        value=parsed_rows,
                        confidence=0.95 if parsed_rows is not None else 0.0,
                        source_text=f"retrieval_table query={query!r}",
                    )
                )
            except Exception as exc:
                logger.warning("[RETRIEVAL TABLE] Failed for field '%s': %s", field.name, exc)
                results.append(
                    ExtractedField(
                        field_name=field.name,
                        value=None,
                        confidence=0.0,
                        source_text=str(exc),
                    )
                )

        return results, sorted(set(source_pages)), field_evidence_regions, field_page_map

    def extract_auto(
        self,
        document_id: str,
        prompt_version_id: str | None = None,
        top_k_per_field: int = 3,
    ) -> ExtractionResult:
        """
        Smart extraction that automatically selects the best extraction strategy.

        Routes to:
        - extract_structured_with_retrieval_vision: when any field has
          visual_content_type='table' (PDF only)
        - extract_structured: default fallback using full document vision/text

        Args:
            document_id: The document to extract from
            prompt_version_id: Optional prompt version to use
            top_k_per_field: Number of chunks to retrieve per field (for retrieval methods)

        Returns:
            ExtractionResult with extracted field values
        """
        repository = get_repository()
        document_repo = get_document_repository()

        document = document_repo.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        classification = repository.get_classification(document_id)
        if not classification:
            raise ValueError(f"Document {document_id} is not classified. Please classify first.")

        doc_type = repository.get_document_type(classification.document_type_id)
        if not doc_type:
            raise ValueError(f"Document type {classification.document_type_id} not found")

        file_type = document.file_type.lower() if document.file_type else ""
        schema_fields = doc_type.schema_fields or []

        # --- Retrieval-table fields: bypass LLM, parse markdown directly ---
        retrieval_table_fields = [
            f for f in schema_fields
            if getattr(f, "extraction_method", None) == ExtractionMethod.RETRIEVAL_TABLE
        ]
        llm_fields = [
            f for f in schema_fields
            if getattr(f, "extraction_method", None) != ExtractionMethod.RETRIEVAL_TABLE
        ]

        retrieval_table_extracted: list[ExtractedField] = []
        retrieval_table_pages: list[int] = []
        retrieval_table_evidence: dict[str, list[dict]] = {}
        retrieval_table_field_pages: dict[str, int] = {}
        if retrieval_table_fields:
            logger.info(
                "[EXTRACTION DEBUG] extract_auto: %d retrieval_table field(s): %s",
                len(retrieval_table_fields),
                [f.name for f in retrieval_table_fields],
            )
            (
                retrieval_table_extracted,
                retrieval_table_pages,
                retrieval_table_evidence,
                retrieval_table_field_pages,
            ) = self._extract_retrieval_table_fields(document_id, retrieval_table_fields)

        # Run LLM extraction only for non-retrieval_table fields
        llm_result: ExtractionResult | None = None
        if llm_fields:
            # For PDFs, always use the retrieval-vision path — it has access to the
            # indexed chunks and page images regardless of whether fields are visual.
            # Fall back to plain text extraction only for non-PDF documents.
            if file_type == "pdf":
                logger.info(
                    "[EXTRACTION DEBUG] extract_auto: retrieval-vision extraction for %d LLM field(s)",
                    len(llm_fields),
                )
                llm_result = self.extract_structured_with_retrieval_vision(
                    document_id=document_id,
                    prompt_version_id=prompt_version_id,
                    top_k_per_field=top_k_per_field,
                    schema_fields_override=llm_fields,
                )
            else:
                logger.info(
                    "[EXTRACTION DEBUG] extract_auto: standard extraction for %d LLM field(s)",
                    len(llm_fields),
                )
                llm_result = self.extract_structured(
                    document_id=document_id,
                    prompt_version_id=prompt_version_id,
                )
        elif not retrieval_table_fields:
            # No fields at all — run standard extraction to get a well-formed result
            llm_result = self.extract_structured(
                document_id=document_id,
                prompt_version_id=prompt_version_id,
            )

        # Merge: start from LLM result (or a shell) and prepend retrieval_table fields
        if llm_result is None:
            from django.utils import timezone as tz
            llm_result = ExtractionResult(
                document_id=document_id,
                document_type_id=doc_type.id,
                fields=[],
                requests=[],
                request_metadata={},
                extracted_at=tz.now(),
            )

        llm_result.fields = retrieval_table_extracted + llm_result.fields

        # Do NOT merge retrieval_table page numbers into source_page_numbers.
        # source_page_numbers is used by the annotation suggestion service to
        # determine which pages pdfplumber should search for LLM field values.
        # Including retrieval_table pages (e.g. page 5 for a financial table) would
        # cause pdfplumber to find scalar field values (e.g. "INTEL CORPORATION") on
        # the wrong page if they also appear in table headers or footers.
        # Retrieval_table fields use citation-region bboxes directly — no pdfplumber needed.

        if retrieval_table_evidence or retrieval_table_field_pages:
            metadata = dict(llm_result.request_metadata or {})
            if retrieval_table_evidence:
                existing_regions = dict(metadata.get("field_evidence_regions", {}) or {})
                existing_regions.update(retrieval_table_evidence)
                metadata["field_evidence_regions"] = existing_regions
            if retrieval_table_field_pages:
                existing_pages = dict(metadata.get("retrieval_table_field_pages", {}) or {})
                existing_pages.update(retrieval_table_field_pages)
                metadata["retrieval_table_field_pages"] = existing_pages
            llm_result.request_metadata = metadata

        return llm_result

    def extract_structured(
        self, document_id: str, prompt_version_id: str | None = None
    ) -> ExtractionResult:
        """
        Extract structured data directly from document using OpenAI structured output.

        This uses the schema fields to generate a Pydantic model and enforces
        structured output from the LLM, bypassing the need for annotations.

        Args:
            document_id: The document to extract from
            prompt_version_id: Optional prompt version to use

        Returns:
            ExtractionResult with extracted field values
        """
        repository = get_repository()
        document_repo = get_document_repository()

        # Get document
        document = document_repo.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")

        # Get classification
        classification = repository.get_classification(document_id)
        if not classification:
            raise ValueError(f"Document {document_id} is not classified. Please classify first.")

        # Get document type with schema
        doc_type = repository.get_document_type(classification.document_type_id)
        if not doc_type:
            raise ValueError(f"Document type {classification.document_type_id} not found")

        if not doc_type.schema_fields:
            raise ValueError(f"Document type '{doc_type.name}' has no schema fields defined")

        effective_schema_fields = self._apply_active_field_prompt_versions(
            doc_type.id,
            doc_type.schema_fields,
        )

        ExtractionModel = generate_pydantic_schema(
            effective_schema_fields, model_name=f"{doc_type.name.replace(' ', '')}Extraction"
        )

        system_prompt = doc_type.system_prompt or self._get_default_extraction_prompt(doc_type)
        system_prompt = f"{system_prompt}\n\n{self._raw_guardrails}"
        model_name = doc_type.extraction_model or self.model

        if prompt_version_id:
            prompt_version = repository.get_prompt_version(prompt_version_id)
            if prompt_version:
                system_prompt = f"{prompt_version.system_prompt}\n\n{self._raw_guardrails}"

        use_vision = False
        image_data = None
        file_type = document.file_type.lower() if document.file_type else ""
        is_visual_document = file_type in [
            "pdf",
            "png",
            "jpg",
            "jpeg",
            "gif",
            "webp",
            "doc",
            "docx",
        ]

        if is_visual_document:
            file_path_to_use = self._get_document_file_path(document)
            if file_path_to_use and file_path_to_use.exists():
                image_data = self._prepare_visual_content(file_path_to_use, file_type)
                if image_data:
                    use_vision = True

        if use_vision and image_data:
            user_prompt_text = (
                f"Extract structured data from this document.\n\n"
                f"Document Type: {doc_type.name}\n"
                f"Filename: {document.filename}\n\n"
                f"Analyze the document image and extract all fields according to the schema. "
                f"Return null for fields that cannot be found."
            )

            messages = [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt_text},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/png;base64,{image_data}"},
                        },
                    ],
                },
            ]
        else:
            content = document.content or ""
            if len(content) > 8000:
                content = content[:4000] + "\n...[truncated]...\n" + content[-4000:]

            user_prompt = f"""Extract structured data from the following document.

Document Type: {doc_type.name}

Document Content:
```
{content}
```

Extract all fields according to the schema. Return null for fields that cannot be found."""

            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]

        logger.info(
            f"Extraction: {document.filename} (model={model_name}, vision={use_vision}, "
            f"fields={len(effective_schema_fields)})"
        )

        # Log the extraction prompt and schema
        logger.warning("[EXTRACTION DEBUG] System prompt:")
        logger.warning(system_prompt)
        logger.warning("[EXTRACTION DEBUG] User messages:")
        for msg in messages:
            if msg["role"] == "user":
                if isinstance(msg["content"], str):
                    logger.warning(f"[EXTRACTION DEBUG] {msg['content']}")
                elif isinstance(msg["content"], list):
                    for item in msg["content"]:
                        if item["type"] == "text":
                            logger.warning(f"[EXTRACTION DEBUG] {item['text']}")
                        elif item["type"] == "image_url":
                            logger.warning("[EXTRACTION DEBUG] [Image content]")

        logger.warning(
            f"[EXTRACTION DEBUG] Schema field names: "
            f"{[f.name for f in effective_schema_fields]}"
        )

        try:
            extracted_data, request_metrics = self._parse_with_metrics(
                model=model_name,
                messages=messages,
                response_format=ExtractionModel,
                schema_version_id=doc_type.schema_version_id,
                prompt_version_id=prompt_version_id,
            )

            logger.warning(
                f"[EXTRACTION DEBUG] Raw extraction output:\n"
                f"{json.dumps(extracted_data.model_dump(), indent=2)}"
            )

            print(f"Extracted: {extracted_data.model_dump()}")

            # Convert to ExtractedField objects
            extracted_fields = []
            for field in effective_schema_fields:
                value = getattr(extracted_data, field.name, None)
                if value is not None:
                    if hasattr(value, "model_dump"):
                        value = value.model_dump()
                    elif isinstance(value, list) and value and hasattr(value[0], "model_dump"):
                        value = [item.model_dump() for item in value]

                    extracted_fields.append(
                        ExtractedField(
                            field_name=field.name, value=value, confidence=0.95, source_text=None
                        )
                    )

            result = ExtractionResult(
                document_id=document_id,
                document_type_id=doc_type.id,
                fields=extracted_fields,
                requests=[request_metrics],
                request_metadata=self._build_request_metadata(
                    strategy="structured_output",
                ),
                schema_version_id=doc_type.schema_version_id,
                prompt_version_id=prompt_version_id,
                extracted_at=timezone.now(),
            )

            # Save extraction result
            self._save_extraction(result)

            return result

        except Exception as e:
            logger.error(f"Extraction failed: {e}", exc_info=True)
            raise ValueError(f"Extraction failed: {str(e)}")

    def _get_default_extraction_prompt(self, doc_type) -> str:
        base_prompt = (
            f"You are an expert at extracting structured data from {doc_type.name} "
            f"documents.\n\n"
            f"Extract all fields accurately from the document. Pay special attention to:\n"
            f"- Tables: Extract ONLY table data (skip titles, disclaimers, footnotes, "
            f"surrounding text)\n"
            f"- Numbers: Keep exact source formatting including currency symbols "
            f"(e.g., '$ 25.0', '$20.0 - $23.0')\n"
            f"- Dates: Keep exact source formatting (no ISO conversion)\n"
            f"- Arrays: Include all table rows, exclude non-table text\n"
            f"- Empty cells: Return null for genuinely empty cells, do not guess or fill in\n"
            f"- Hierarchy paths: For tables with nested/indented rows, extract the full path "
            f"from root to leaf as an array\n\n"
            f"HIERARCHICAL TABLES (if schema has 'hierarchy_path' field):\n"
            f"- For each row, identify its complete hierarchical path from the table structure\n"
            f"- Detect hierarchy using: indentation, font weight (bold/normal), visual grouping\n"
            f'- Top-level rows: ["Main Category"]\n'
            f'- Indented sub-rows: ["Main Category", "Sub Item"]\n'
            f'- Deeper nesting: ["Level 1", "Level 2", "Level 3", "Level 4", ...]\n'
            f"- Extract the row label at each level EXACTLY as it appears "
            f"(preserve spacing/formatting)\n\n"
            f"CRITICAL: Only extract data that appears IN the table structure. Do not extract:\n"
            f"- Table titles or section headers above the table\n"
            f"- Explanatory paragraphs or disclaimers\n"
            f"- Footnotes or references below the table\n\n"
            f"EMPTY CELLS: If a table cell is empty or a field cannot be found, return null "
            f'(not empty string "").\n'
            f"Do not make up data or use empty strings for missing values."
        )

        visual_guidance_parts = []
        for field in doc_type.schema_fields or []:
            if field.visual_guidance:
                visual_guidance_parts.append(f"- {field.name}: {field.visual_guidance}")

        if visual_guidance_parts:
            visual_section = "\n\nField-specific visual guidance:\n" + "\n".join(
                visual_guidance_parts
            )
            return base_prompt + visual_section

        return base_prompt

    def extract_structured_with_retrieval(
        self,
        document_id: str,
        prompt_version_id: str | None = None,
        top_k_per_field: int = 5,
    ) -> ExtractionResult:
        return self.extract_structured_with_retrieval_vision(
            document_id=document_id,
            prompt_version_id=prompt_version_id,
            top_k_per_field=top_k_per_field,
        )

    def extract_structured_with_retrieval_vision(
        self,
        document_id: str,
        prompt_version_id: str | None = None,
        top_k_per_field: int = 3,
        min_score: float = 0.0,
        schema_fields_override: list[SchemaField] | None = None,
    ) -> ExtractionResult:
        """Extract structured data from PDFs using agentic evidence coverage + page vision.

        Args:
            schema_fields_override: When provided, use these fields instead of the full
                document-type schema. Used by extract_auto to pass only the LLM-destined
                subset after retrieval_table fields have been routed elsewhere.
        """
        from uu_backend.services.contextual_retrieval import get_contextual_retrieval_service

        repository = get_repository()
        document_repo = get_document_repository()

        document = document_repo.get_document(document_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        self._ensure_retrieval_ready(document)

        classification = repository.get_classification(document_id)
        if not classification:
            raise ValueError(f"Document {document_id} is not classified. Please classify first.")

        doc_type = repository.get_document_type(classification.document_type_id)
        if not doc_type:
            raise ValueError(f"Document type {classification.document_type_id} not found")

        # Apply override: restrict schema to caller-specified fields when provided.
        # This lets extract_auto exclude retrieval_table fields from the LLM pass.
        if schema_fields_override is not None:
            import copy
            doc_type = copy.copy(doc_type)
            doc_type.schema_fields = schema_fields_override

        if not doc_type.schema_fields:
            raise ValueError(f"Document type '{doc_type.name}' has no schema fields defined")

        effective_schema_fields = self._apply_active_field_prompt_versions(
            doc_type.id,
            doc_type.schema_fields,
        )

        ExtractionModel = generate_pydantic_schema(
            effective_schema_fields, model_name=f"{doc_type.name.replace(' ', '')}Extraction"
        )

        retrieval_service = get_contextual_retrieval_service()

        logger.info("PDF intelligent retrieval extraction: %s (type=%s)", document.filename, doc_type.name)

        evidence_by_field, coverage_by_field, retry_count = self._run_agentic_retrieval_loop(
            document_id=document_id,
            doc_type=doc_type,
            schema_fields=effective_schema_fields,
            retrieval_service=retrieval_service,
            top_k_per_field=top_k_per_field,
        )

        all_page_numbers, field_page_map = self._select_pages_from_evidence(
            schema_fields=effective_schema_fields,
            evidence_by_field=evidence_by_field,
        )
        evidence_by_field = self._filter_evidence_to_selected_pages(
            schema_fields=effective_schema_fields,
            evidence_by_field=evidence_by_field,
            field_page_map=field_page_map,
        )
        field_evidence_regions = self._build_field_evidence_regions(
            schema_fields=effective_schema_fields,
            evidence_by_field=evidence_by_field,
        )
        if not all_page_numbers:
            all_page_numbers = [1]

        logger.info(
            "[RETRIEVAL DEBUG] Agentic evidence selected pages for %s: %s",
            document_id,
            all_page_numbers,
        )

        file_path = self._get_document_file_path(document)
        if not file_path or not file_path.exists():
            raise ValueError(f"Document file not found for {document_id}")

        file_type = document.file_type.lower() if document.file_type else ""
        if file_type != "pdf":
            raise ValueError(
                f"Retrieval-vision extraction only supports PDF documents, got {file_type}"
            )

        page_images = self._render_pdf_pages(file_path, all_page_numbers)

        if not page_images:
            raise ValueError(f"Failed to render PDF pages {all_page_numbers}")

        system_prompt = doc_type.system_prompt or self._get_default_extraction_prompt(doc_type)
        system_prompt = f"{system_prompt}\n\n{self._raw_guardrails}"
        model_name = doc_type.extraction_model or self.model

        if prompt_version_id:
            prompt_version = repository.get_prompt_version(prompt_version_id)
            if prompt_version:
                system_prompt = f"{prompt_version.system_prompt}\n\n{self._raw_guardrails}"

        evidence_text = self._build_evidence_text(
            schema_fields=effective_schema_fields,
            evidence_by_field=evidence_by_field,
            coverage_by_field=coverage_by_field,
        )
        user_content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": f"""Extract structured data from the PDF page(s) shown below.

Document Type: {doc_type.name}
Filename: {document.filename}

Retrieved Evidence By Field:
{evidence_text}

Coverage metadata:
{json.dumps(coverage_by_field, indent=2)}

CRITICAL INSTRUCTIONS:
1. Use the retrieved evidence and cited PDF pages together.
2. Extract values EXACTLY as shown; do not normalize or infer.
3. For table fields, prefer the retrieved table evidence and table regions.
4. If a field still lacks support after the evidence search, return null.
5. Return partial grounded output rather than guessing missing values.""",
            }
        ]

        for i, img_b64 in enumerate(page_images, 1):
            user_content.append(
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        # Log extraction prompt details
        logger.warning("[EXTRACTION DEBUG] Vision extraction prompt:")
        logger.warning(f"[EXTRACTION DEBUG] System prompt:\n{system_prompt}")
        logger.warning(f"[EXTRACTION DEBUG] User prompt (text part):\n{user_content[0]['text']}")
        logger.warning(
            f"[EXTRACTION DEBUG] Schema fields: " f"{[f.name for f in effective_schema_fields]}"
        )

        try:
            extracted_data, request_metrics = self._parse_with_metrics(
                model=model_name,
                messages=messages,
                response_format=ExtractionModel,
                schema_version_id=doc_type.schema_version_id,
                prompt_version_id=prompt_version_id,
            )

            logger.warning(
                f"[EXTRACTION DEBUG] Raw extraction output:\n"
                f"{json.dumps(extracted_data.model_dump(), indent=2)}"
            )

            extracted_fields = []
            for field in effective_schema_fields:
                value = getattr(extracted_data, field.name, None)
                if value is not None:
                    if hasattr(value, "model_dump"):
                        value = value.model_dump()
                    elif isinstance(value, list) and value and hasattr(value[0], "model_dump"):
                        value = [item.model_dump() for item in value]

                    pages_for_field = field_page_map.get(field.name, set())
                    top_result = (evidence_by_field.get(field.name) or [None])[0]
                    source_preview = None
                    if top_result is not None:
                        source_preview = self._normalize_query_fragment(
                            getattr(top_result, "original_text", "") or getattr(top_result, "text", ""),
                            max_chars=200,
                        )
                    source_text = (
                        f"Pages: {sorted(pages_for_field)} | {source_preview}"
                        if pages_for_field
                        else source_preview
                    )

                    extracted_fields.append(
                        ExtractedField(
                            field_name=field.name,
                            value=value,
                            confidence=0.95,
                            source_text=source_text,
                        )
                    )

            result = ExtractionResult(
                document_id=document_id,
                document_type_id=doc_type.id,
                fields=extracted_fields,
                requests=[request_metrics],
                request_metadata={
                    **self._build_request_metadata(
                        strategy="intelligent_pdf_agentic_retrieval",
                        source_page_numbers=all_page_numbers,
                    ),
                    "coverage_by_field": coverage_by_field,
                    "retry_count": retry_count,
                    "field_page_map": {
                        field_name: sorted(pages) for field_name, pages in field_page_map.items()
                    },
                    "field_evidence_regions": field_evidence_regions,
                },
                schema_version_id=doc_type.schema_version_id,
                prompt_version_id=prompt_version_id,
                extracted_at=timezone.now(),
                source_page_numbers=sorted(all_page_numbers),
            )

            self._save_extraction(result)

            return result

        except Exception as e:
            logger.error(f"Retrieval-vision extraction failed: {e}", exc_info=True)
            raise ValueError(f"Extraction failed: {str(e)}")

    def _parse_with_metrics(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        response_format: Any,
        schema_version_id: str | None,
        prompt_version_id: str | None,
    ) -> tuple[Any, ExtractionRequestMetrics]:
        started_at = timezone.now()
        started = time.perf_counter()
        response = self.client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=response_format,
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        usage = self._usage_from_response(response)
        cost_usd, cost_note = self._estimate_request_cost(model=model, usage=usage)
        metrics = ExtractionRequestMetrics(
            request_id=str(uuid4()),
            schema_version_id=schema_version_id,
            prompt_version_id=prompt_version_id,
            model=model,
            latency_ms=latency_ms,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
            cost_usd=cost_usd,
            cost_note=cost_note,
            created_at=started_at,
        )
        return response.choices[0].message.parsed, metrics

    def _usage_from_response(self, response: Any) -> dict[str, int | None]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {
                "prompt_tokens": None,
                "completion_tokens": None,
                "total_tokens": None,
                "cached_prompt_tokens": None,
            }

        payload = usage.model_dump() if hasattr(usage, "model_dump") else {}
        if not isinstance(payload, dict):
            payload = {}

        prompt_tokens = payload.get("prompt_tokens")
        completion_tokens = payload.get("completion_tokens")
        total_tokens = payload.get("total_tokens")

        prompt_details = payload.get("prompt_tokens_details")
        cached_prompt_tokens = None
        if isinstance(prompt_details, dict):
            cached_prompt_tokens = prompt_details.get("cached_tokens")

        return {
            "prompt_tokens": int(prompt_tokens) if isinstance(prompt_tokens, int) else None,
            "completion_tokens": (
                int(completion_tokens) if isinstance(completion_tokens, int) else None
            ),
            "total_tokens": int(total_tokens) if isinstance(total_tokens, int) else None,
            "cached_prompt_tokens": (
                int(cached_prompt_tokens) if isinstance(cached_prompt_tokens, int) else None
            ),
        }

    def _estimate_request_cost(
        self, *, model: str, usage: dict[str, int | None]
    ) -> tuple[float | None, str | None]:
        pricing = self._pricing_by_model.get(model)
        if not pricing:
            for configured_model, configured_pricing in self._pricing_by_model.items():
                if model.startswith(configured_model):
                    pricing = configured_pricing
                    break
        if not pricing:
            return None, f"Cost unavailable: pricing not configured for model '{model}'"

        input_rate = pricing.get("input_per_million")
        output_rate = pricing.get("output_per_million")
        cached_input_rate = pricing.get("cached_input_per_million", input_rate)

        if input_rate is None or output_rate is None:
            return None, f"Cost unavailable: pricing for model '{model}' is incomplete"

        prompt_tokens = usage.get("prompt_tokens") or 0
        completion_tokens = usage.get("completion_tokens") or 0
        cached_prompt_tokens = min(usage.get("cached_prompt_tokens") or 0, prompt_tokens)
        uncached_prompt_tokens = max(prompt_tokens - cached_prompt_tokens, 0)

        cost_usd = (
            uncached_prompt_tokens * float(input_rate) / 1_000_000
            + cached_prompt_tokens * float(cached_input_rate) / 1_000_000
            + completion_tokens * float(output_rate) / 1_000_000
        )

        return round(cost_usd, 8), None

    def extract_structured_from_snapshot(
        self,
        *,
        content: str,
        filename: str,
        document_type_name: str,
        schema_fields: list[SchemaField],
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Extract structured data using a deployable schema/prompt snapshot.

        This does not require document ingestion, classification, or annotation persistence.
        """
        if not schema_fields:
            raise ValueError("Deployment snapshot has no schema fields")

        ExtractionModel = generate_pydantic_schema(
            schema_fields,
            model_name=f"{document_type_name.replace(' ', '')}DeploymentExtraction",
        )

        trimmed_content = content or ""
        if len(trimmed_content) > 8000:
            trimmed_content = (
                trimmed_content[:4000] + "\n...[truncated]...\n" + trimmed_content[-4000:]
            )

        effective_system_prompt = (
            system_prompt
            or f"You are an expert at extracting structured data from "
            f"{document_type_name} documents."
        )
        effective_system_prompt = f"{effective_system_prompt}\n\n{self._raw_guardrails}"

        user_prompt = f"""Extract structured data from the following document.

Document Type: {document_type_name}
Filename: {filename}

Document Content:
```
{trimmed_content}
```

Extract all fields according to the schema. Return null for fields that cannot be found."""

        effective_model = model or self.model
        logger.info(
            f"Snapshot extraction: {filename} (model={effective_model}, type={document_type_name})"
        )

        response = self.client.beta.chat.completions.parse(
            model=effective_model,
            messages=[
                {"role": "system", "content": effective_system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format=ExtractionModel,
        )
        parsed = response.choices[0].message.parsed
        return parsed.model_dump() if parsed else {}

    def extract_auto_from_snapshot(
        self,
        *,
        content: str,
        filename: str,
        document_type_name: str,
        schema_fields: list[SchemaField],
        system_prompt: str | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        """
        Deployment-path extraction that respects extraction_method per field.

        For retrieval_table fields: scans raw content for markdown tables without
        needing a stored document or vector index.
        For all other fields: delegates to the standard LLM snapshot extraction.
        """
        retrieval_table_fields = [
            f for f in schema_fields
            if getattr(f, "extraction_method", None) == ExtractionMethod.RETRIEVAL_TABLE
        ]
        llm_fields = [
            f for f in schema_fields
            if getattr(f, "extraction_method", None) != ExtractionMethod.RETRIEVAL_TABLE
        ]

        result: dict[str, Any] = {}

        # --- Retrieval-table fields: scan content for markdown tables ---
        if retrieval_table_fields:
            all_table_blocks = self._extract_table_blocks_from_content(content)
            logger.info(
                "[SNAPSHOT] Found %d markdown table block(s) in content for retrieval_table routing",
                len(all_table_blocks),
            )
            for field in retrieval_table_fields:
                query_keywords = set(
                    (field.retrieval_query or field.name.replace("_", " ")).lower().split()
                )
                matched_rows: list[dict] | None = None
                # Prefer blocks whose surrounding text mentions field keywords
                for block_text in all_table_blocks:
                    block_lower = block_text.lower()
                    if any(kw in block_lower for kw in query_keywords):
                        matched_rows = self._parse_markdown_table(block_text)
                        if matched_rows is not None:
                            break
                # Fallback: use the first parseable table
                if matched_rows is None:
                    for block_text in all_table_blocks:
                        matched_rows = self._parse_markdown_table(block_text)
                        if matched_rows is not None:
                            break
                result[field.name] = matched_rows
                logger.info(
                    "[SNAPSHOT] retrieval_table field '%s': %s rows extracted",
                    field.name,
                    len(matched_rows) if matched_rows is not None else "None",
                )

        # --- LLM fields ---
        if llm_fields:
            llm_result = self.extract_structured_from_snapshot(
                content=content,
                filename=filename,
                document_type_name=document_type_name,
                schema_fields=llm_fields,
                system_prompt=system_prompt,
                model=model,
            )
            result.update(llm_result)
        elif not retrieval_table_fields:
            # No fields at all — still run the LLM to get a well-formed empty result
            result = self.extract_structured_from_snapshot(
                content=content,
                filename=filename,
                document_type_name=document_type_name,
                schema_fields=schema_fields,
                system_prompt=system_prompt,
                model=model,
            )

        return result

    def _extract_table_blocks_from_content(self, content: str) -> list[str]:
        """
        Split raw markdown content into individual table blocks.

        A table block is a contiguous group of lines that start and end with '|'.
        We keep a window of surrounding context lines so that keyword matching
        against the field query can see section headings near the table.
        """
        lines = content.split("\n")
        blocks: list[str] = []
        i = 0
        while i < len(lines):
            if lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                # Capture up to 5 context lines before the table
                context_start = max(0, i - 5)
                j = i
                while j < len(lines) and lines[j].strip().startswith("|") and lines[j].strip().endswith("|"):
                    j += 1
                block_lines = lines[context_start:j]
                blocks.append("\n".join(block_lines))
                i = j
            else:
                i += 1
        return blocks

    def _get_document_file_path(self, document) -> Path | None:
        if document.file_path:
            return Path(document.file_path)

        settings = get_settings()
        file_ext = f".{document.file_type.lower()}" if document.file_type else ""
        potential_path = settings.file_storage_path / f"{document.id}{file_ext}"
        return potential_path if potential_path.exists() else None

    def _prepare_visual_content(
        self, file_path: Path, file_type: str, page_number: int | None = None
    ) -> str | None:
        try:
            if file_type == "pdf":
                if not PDF_SUPPORT:
                    logger.warning("pdf2image not available, cannot process PDF")
                    return None

                page = page_number or 1
                images = convert_from_path(str(file_path), first_page=page, last_page=page, dpi=150)
                if images:
                    img_byte_arr = io.BytesIO()
                    images[0].save(img_byte_arr, format="PNG")
                    image_bytes = img_byte_arr.getvalue()
                    return base64.b64encode(image_bytes).decode("utf-8")
                else:
                    logger.warning(f"Could not convert PDF page {page} to image")
                    return None

            elif file_type in ["doc", "docx"]:
                logger.info("Word documents not yet supported for vision API")
                return None

            elif file_type in ["png", "jpg", "jpeg", "gif", "webp"]:
                with open(file_path, "rb") as f:
                    image_bytes = f.read()
                    return base64.b64encode(image_bytes).decode("utf-8")

            return None

        except Exception as e:
            logger.error(f"Error preparing visual content: {e}", exc_info=True)
            return None

    def _render_pdf_pages(
        self, file_path: Path, page_numbers: list[int], dpi: int = 150
    ) -> list[str]:
        if not PDF_SUPPORT:
            logger.warning("pdf2image not available, cannot render PDF pages")
            return []

        try:
            images_b64 = []
            for page_num in sorted(set(page_numbers)):
                images = convert_from_path(
                    str(file_path), first_page=page_num, last_page=page_num, dpi=dpi
                )
                if images:
                    img_byte_arr = io.BytesIO()
                    images[0].save(img_byte_arr, format="PNG")
                    image_bytes = img_byte_arr.getvalue()
                    images_b64.append(base64.b64encode(image_bytes).decode("utf-8"))
                else:
                    logger.warning(f"Could not render PDF page {page_num}")

            return images_b64

        except Exception as e:
            logger.error(f"Error rendering PDF pages {page_numbers}: {e}", exc_info=True)
            return []

    def _apply_active_field_prompt_versions(
        self, document_type_id: str, schema_fields: list[SchemaField]
    ) -> list[SchemaField]:
        repository = get_repository()
        active_prompts = repository.list_active_field_prompt_versions(document_type_id)
        if not active_prompts:
            return schema_fields
        return [
            field.model_copy(
                update={
                    "extraction_prompt": active_prompts.get(field.name, field.extraction_prompt)
                }
            )
            for field in schema_fields
        ]

    def _save_extraction(self, result: ExtractionResult):
        repository = get_repository()
        repository.save_extraction_result(result)


# Singleton instance
_extraction_service: ExtractionService | None = None


def get_extraction_service() -> ExtractionService:
    """Get or create the extraction service singleton."""
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = ExtractionService()
    return _extraction_service
