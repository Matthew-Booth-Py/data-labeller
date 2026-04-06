"""Azure Document Intelligence integration for PDF retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from io import BytesIO
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential


@dataclass(slots=True)
class NormalizedLine:
    text: str
    bbox: list[float]


@dataclass(slots=True)
class NormalizedPage:
    page_number: int
    width: float
    height: float
    text: str = ""
    lines: list[NormalizedLine] = field(default_factory=list)


@dataclass(slots=True)
class NormalizedTable:
    page_number: int
    bbox: list[float]
    markdown: str
    row_count: int
    column_count: int


@dataclass(slots=True)
class NormalizedFigure:
    page_number: int
    bbox: list[float]
    caption: str = ""


@dataclass(slots=True)
class NormalizedDocumentAnalysis:
    pages: list[NormalizedPage] = field(default_factory=list)
    tables: list[NormalizedTable] = field(default_factory=list)
    figures: list[NormalizedFigure] = field(default_factory=list)


def _polygon_to_bbox(polygon: list[float] | None) -> list[float]:
    if not polygon:
        return []
    xs = polygon[::2]
    ys = polygon[1::2]
    return [float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))]


class AzureDocumentIntelligenceProvider:
    """Thin sync adapter around Azure Document Intelligence."""

    def __init__(self, endpoint: str, api_key: str):
        if not endpoint or not api_key:
            raise ValueError("AZURE_DI_ENDPOINT and AZURE_DI_KEY are required for PDF retrieval")
        self.client = DocumentIntelligenceClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
        )

    def analyze_pdf(self, pdf_bytes: bytes) -> NormalizedDocumentAnalysis:
        """Submit a PDF to Azure Document Intelligence and return a normalised analysis."""
        poller = self.client.begin_analyze_document(
            "prebuilt-layout",
            body=BytesIO(pdf_bytes),
            content_type="application/octet-stream",
            output_content_format="markdown",
        )
        result = poller.result()
        return self._normalize_result(result)

    def _normalize_result(self, result: Any) -> NormalizedDocumentAnalysis:
        normalized = NormalizedDocumentAnalysis()

        for page in getattr(result, "pages", []) or []:
            normalized_lines = [
                NormalizedLine(
                    text=str(getattr(line, "content", "") or ""),
                    bbox=_polygon_to_bbox(getattr(line, "polygon", None)),
                )
                for line in getattr(page, "lines", []) or []
                if str(getattr(line, "content", "") or "").strip()
            ]
            normalized.pages.append(
                NormalizedPage(
                    page_number=int(page.page_number),
                    width=float(page.width or 0.0),
                    height=float(page.height or 0.0),
                    text="\n".join(line.text for line in normalized_lines if line.text),
                    lines=normalized_lines,
                )
            )

        for table in getattr(result, "tables", []) or []:
            regions = getattr(table, "bounding_regions", []) or []
            region = regions[0] if regions else None
            normalized.tables.append(
                NormalizedTable(
                    page_number=int(getattr(region, "page_number", 1) or 1),
                    bbox=_polygon_to_bbox(getattr(region, "polygon", None)),
                    markdown=self._table_to_markdown(table),
                    row_count=int(getattr(table, "row_count", 0) or 0),
                    column_count=int(getattr(table, "column_count", 0) or 0),
                )
            )

        for figure in getattr(result, "figures", []) or []:
            regions = getattr(figure, "bounding_regions", []) or []
            region = regions[0] if regions else None
            caption_obj = getattr(figure, "caption", None)
            normalized.figures.append(
                NormalizedFigure(
                    page_number=int(getattr(region, "page_number", 1) or 1),
                    bbox=_polygon_to_bbox(getattr(region, "polygon", None)),
                    caption=str(getattr(caption_obj, "content", "") or ""),
                )
            )

        return normalized

    def _table_to_markdown(self, table: Any) -> str:
        row_count = int(getattr(table, "row_count", 0) or 0)
        column_count = int(getattr(table, "column_count", 0) or 0)
        if row_count <= 0 or column_count <= 0:
            return ""

        grid = [["" for _ in range(column_count)] for _ in range(row_count)]
        for cell in getattr(table, "cells", []) or []:
            row_index = int(getattr(cell, "row_index", 0) or 0)
            column_index = int(getattr(cell, "column_index", 0) or 0)
            content = str(getattr(cell, "content", "") or "").replace("\n", " ").strip()
            if 0 <= row_index < row_count and 0 <= column_index < column_count:
                grid[row_index][column_index] = content

        header = "| " + " | ".join(grid[0]) + " |"
        separator = "| " + " | ".join(["---"] * column_count) + " |"
        rows = ["| " + " | ".join(row) + " |" for row in grid[1:]]
        return "\n".join([header, separator, *rows])
