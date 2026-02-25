"""Document conversion using MarkItDown and pdfplumber for enhanced table extraction."""

import re
import tempfile
from collections import deque
from pathlib import Path
from typing import BinaryIO

import pdfplumber
from markitdown import MarkItDown

from uu_backend.models.document import DocumentMetadata


class ConversionResult:
    """Result of converting a document to markdown."""

    def __init__(
        self,
        content: str,
        metadata: DocumentMetadata,
        success: bool = True,
        error: str | None = None,
    ):
        self.content = content
        self.metadata = metadata
        self.success = success
        self.error = error


def _normalize_for_dedupe(line: str) -> str:
    """Create a normalized representation of a line for duplicate checks."""
    normalized = re.sub(r"\s+", " ", line.strip().lower())
    normalized = re.sub(r"[^\w\s|:.$-]", "", normalized)
    return normalized


def _repair_table_header_fragments(line: str) -> str:
    """Repair common split-header artifacts from table extraction."""
    repaired = line
    # Example observed: "Damage Description E | st. Replacement Cost"
    repaired = repaired.replace(
        "Damage Description E | st. Replacement Cost", "Damage Description | Est. Replacement Cost"
    )
    repaired = re.sub(r"\bE\s*\|\s*st\.", "Est.", repaired)
    return repaired


def _move_total_after_following_table(lines: list[str]) -> list[str]:
    """If TOTAL line appears before immediately following markdown table rows, move it below the table."""
    i = 0
    out: list[str] = []
    while i < len(lines):
        line = lines[i]
        if re.match(r"^\s*TOTAL\b", line, flags=re.IGNORECASE):
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].lstrip().startswith("|"):
                table_block: list[str] = []
                k = j
                while k < len(lines) and lines[k].lstrip().startswith("|"):
                    table_block.append(lines[k])
                    k += 1
                out.extend(table_block)
                out.append(line)
                i = k
                continue
        out.append(line)
        i += 1
    return out


def _normalize_key_value_blocks(lines: list[str]) -> list[str]:
    """Convert contiguous key-value lines into markdown tables for consistent formatting."""
    kv_pattern = re.compile(r"^\s*([A-Za-z][A-Za-z0-9 /()&\-.]{1,50}):\s+(.+?)\s*$")
    out: list[str] = []
    i = 0
    while i < len(lines):
        match = kv_pattern.match(lines[i])
        if not match:
            out.append(lines[i])
            i += 1
            continue

        block: list[tuple[str, str]] = []
        j = i
        while j < len(lines):
            m = kv_pattern.match(lines[j])
            if not m:
                break
            key = m.group(1).strip()
            value = m.group(2).strip()
            block.append((key, value))
            j += 1

        # Only normalize sufficiently large blocks to avoid over-formatting incidental pairs.
        if len(block) >= 3:
            out.append("| Field | Value |")
            out.append("| --- | --- |")
            for key, value in block:
                out.append(f"| {key} | {value} |")
        else:
            for key, value in block:
                out.append(f"{key}: {value}")
        i = j
    return out


def _dedupe_lines(lines: list[str]) -> list[str]:
    """Remove repeated nearby lines caused by layout extraction overlap."""
    recent = deque(maxlen=24)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            out.append(line)
            continue
        if stripped.startswith("|") or stripped.startswith("## Page"):
            out.append(line)
            recent.append(_normalize_for_dedupe(line))
            continue

        marker = _normalize_for_dedupe(line)
        if marker and marker in recent:
            continue
        out.append(line)
        recent.append(marker)
    return out


def postprocess_markdown(content: str) -> str:
    """Apply deterministic formatting repairs to extracted markdown content."""
    if not content.strip():
        return content

    lines = content.splitlines()
    lines = [_repair_table_header_fragments(line) for line in lines]
    lines = _dedupe_lines(lines)
    lines = _move_total_after_following_table(lines)
    lines = _normalize_key_value_blocks(lines)

    text = "\n".join(lines)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text


def table_to_markdown(table: list[list[str | None]]) -> str:
    """Convert a table (list of rows) to markdown format."""
    if not table or len(table) == 0:
        return ""

    # Clean up cells - replace None with empty string
    cleaned = []
    for row in table:
        cleaned.append([str(cell).strip() if cell else "" for cell in row])

    if len(cleaned) == 0:
        return ""

    # Determine column count from the widest row
    col_count = max(len(row) for row in cleaned)

    # Pad rows to have equal columns
    for row in cleaned:
        while len(row) < col_count:
            row.append("")

    # Build markdown table
    lines = []

    # Header row
    header = cleaned[0]
    lines.append("| " + " | ".join(header) + " |")

    # Separator
    lines.append("| " + " | ".join(["---"] * col_count) + " |")

    # Data rows
    for row in cleaned[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def extract_pdf_with_tables(pdf_path: str) -> tuple[str, int]:
    """
    Extract text and tables from PDF using pdfplumber.

    Returns tuple of (content, page_count).
    Uses layout-preserving text extraction which maintains tabular alignment.
    Bordered tables are converted to markdown format when detected.
    """
    content_parts = []
    page_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, 1):
            page_content = []

            # Try to extract bordered tables first
            # Use lines-based detection for actual bordered tables
            table_settings = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
            }
            bordered_tables = page.extract_tables(table_settings)

            if bordered_tables and any(len(t) > 1 for t in bordered_tables if t):
                # Found bordered tables - need to preserve order with text
                page_content.append(f"\n## Page {page_num}\n")

                # Get table bounding boxes
                table_bboxes = [
                    table.bbox for table in page.find_tables(table_settings) if table.bbox
                ]

                # Expand bounding boxes with generous padding to catch all table-related text
                expanded_bboxes = []
                for bbox in table_bboxes:
                    # Add 10 pixels of padding vertically to catch headers/footers
                    expanded_bboxes.append(
                        (
                            bbox[0] - 2,  # x0 - minimal horizontal padding
                            bbox[1] - 10,  # y0 - generous top padding
                            bbox[2] + 2,  # x1
                            bbox[3] + 10,  # y1 - generous bottom padding
                        )
                    )

                # Get all words with their positions
                words = page.extract_words()

                # Filter words that are NOT in table regions
                non_table_words = []
                for word in words:
                    word_bbox = (word["x0"], word["top"], word["x1"], word["bottom"])
                    in_table = False

                    for table_bbox in expanded_bboxes:
                        # Check if word overlaps with table bbox
                        if word_bbox[1] >= table_bbox[1] and word_bbox[3] <= table_bbox[3]:
                            # Word's vertical position is within table region
                            in_table = True
                            break

                    if not in_table:
                        non_table_words.append(word)

                # Reconstruct text from non-table words, preserving layout
                if non_table_words:
                    # Sort by vertical position, then horizontal
                    non_table_words.sort(key=lambda w: (w["top"], w["x0"]))

                    # Group words into lines based on vertical position
                    lines = []
                    current_line = []
                    current_y = None
                    y_tolerance = 3

                    for word in non_table_words:
                        if current_y is None or abs(word["top"] - current_y) <= y_tolerance:
                            current_line.append(word["text"])
                            current_y = word["top"] if current_y is None else current_y
                        else:
                            if current_line:
                                lines.append(" ".join(current_line))
                            current_line = [word["text"]]
                            current_y = word["top"]

                    if current_line:
                        lines.append(" ".join(current_line))

                    non_table_text = "\n".join(lines).strip()
                else:
                    non_table_text = ""

                # Add non-table text first (document header, etc.)
                if non_table_text:
                    page_content.append(f"\n{non_table_text}\n")

                # Then add tables in order
                for i, table in enumerate(bordered_tables):
                    if table and len(table) > 1:
                        md_table = table_to_markdown(table)
                        if md_table:
                            page_content.append(f"\n{md_table}\n")
            else:
                # No bordered tables - use layout-preserving text extraction
                # This preserves whitespace alignment for financial tables
                text = (
                    page.extract_text(
                        layout=True,  # Preserve layout/spacing
                        x_tolerance=2,
                        y_tolerance=2,
                    )
                    or ""
                )

                if text.strip():
                    # Add page header for multi-page documents
                    if page_count > 1:
                        page_content.append(f"\n--- Page {page_num} ---\n")
                    page_content.append(text)

            if page_content:
                content_parts.append("\n".join(page_content))

    return "\n\n".join(content_parts), page_count


class DocumentConverter:
    """Wrapper around MarkItDown for document conversion with enhanced PDF table support."""

    # Supported file extensions
    SUPPORTED_EXTENSIONS = {
        ".pdf",
        ".docx",
        ".doc",
        ".xlsx",
        ".xls",
        ".pptx",
        ".ppt",
        ".html",
        ".htm",
        ".txt",
        ".md",
        ".csv",
        ".json",
        ".xml",
        ".jpg",
        ".jpeg",
        ".png",
        ".gif",
        ".webp",
        ".eml",
        ".msg",
    }

    def __init__(self):
        """Initialize the MarkItDown converter."""
        self._converter = MarkItDown()

    def convert(
        self,
        file: BinaryIO,
        filename: str,
    ) -> ConversionResult:
        """
        Convert a file to markdown.

        Args:
            file: File-like object with the document content
            filename: Original filename for extension detection

        Returns:
            ConversionResult with markdown content and metadata
        """
        file_path = Path(filename)
        extension = file_path.suffix.lower()
        temp_path = None

        # Validate extension
        if extension not in self.SUPPORTED_EXTENSIONS:
            return ConversionResult(
                content="",
                metadata=DocumentMetadata(
                    filename=filename,
                    file_type=extension.lstrip(".") or "unknown",
                ),
                success=False,
                error=f"Unsupported file type: {extension}",
            )

        # Write to temp file for processing
        try:
            with tempfile.NamedTemporaryFile(
                suffix=extension,
                delete=False,
            ) as temp_file:
                temp_path = Path(temp_file.name)
                content = file.read()
                temp_file.write(content)
                file_size = len(content)

            # Use pdfplumber for PDFs (better table extraction)
            if extension == ".pdf":
                text_content, page_count = extract_pdf_with_tables(str(temp_path))
                text_content = postprocess_markdown(text_content)
                metadata = DocumentMetadata(
                    filename=filename,
                    file_type=extension.lstrip("."),
                    file_size=file_size,
                    page_count=page_count,
                )
            else:
                # Use MarkItDown for other formats
                result = self._converter.convert(str(temp_path))
                text_content = postprocess_markdown(result.text_content)
                metadata = DocumentMetadata(
                    filename=filename,
                    file_type=extension.lstrip("."),
                    file_size=file_size,
                )

            return ConversionResult(
                content=text_content,
                metadata=metadata,
                success=True,
            )

        except Exception as e:
            return ConversionResult(
                content="",
                metadata=DocumentMetadata(
                    filename=filename,
                    file_type=extension.lstrip(".") or "unknown",
                ),
                success=False,
                error=str(e),
            )

        finally:
            # Cleanup temp file
            if temp_path and temp_path.exists():
                temp_path.unlink()

    def is_supported(self, filename: str) -> bool:
        """Check if a file type is supported."""
        extension = Path(filename).suffix.lower()
        return extension in self.SUPPORTED_EXTENSIONS


# Module-level instance for convenience
_converter: DocumentConverter | None = None


def get_converter() -> DocumentConverter:
    """Get or create a DocumentConverter instance."""
    global _converter
    if _converter is None:
        _converter = DocumentConverter()
    return _converter
