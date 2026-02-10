"""Document conversion using MarkItDown and pdfplumber for enhanced table extraction."""

import tempfile
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
                # Found bordered tables - convert to markdown
                page_content.append(f"\n## Page {page_num}\n")

                for i, table in enumerate(bordered_tables):
                    if table and len(table) > 1:
                        md_table = table_to_markdown(table)
                        if md_table:
                            page_content.append(f"\n{md_table}\n")

                # Extract text outside of tables by filtering out table bounding boxes
                # This prevents duplication of table content
                table_bboxes = [table.bbox for table in page.find_tables(table_settings) if table.bbox]
                
                # Get all text objects
                words = page.extract_words()
                non_table_text = []
                
                for word in words:
                    word_bbox = (word['x0'], word['top'], word['x1'], word['bottom'])
                    # Check if word is inside any table bbox
                    in_table = False
                    for table_bbox in table_bboxes:
                        if (word_bbox[0] >= table_bbox[0] and word_bbox[2] <= table_bbox[2] and
                            word_bbox[1] >= table_bbox[1] and word_bbox[3] <= table_bbox[3]):
                            in_table = True
                            break
                    
                    if not in_table:
                        non_table_text.append(word['text'])
                
                # Add non-table text if any
                if non_table_text:
                    page_content.append(f"\n{' '.join(non_table_text)}\n")
            else:
                # No bordered tables - use layout-preserving text extraction
                # This preserves whitespace alignment for financial tables
                text = page.extract_text(
                    layout=True,  # Preserve layout/spacing
                    x_tolerance=2,
                    y_tolerance=2,
                ) or ""

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
                metadata = DocumentMetadata(
                    filename=filename,
                    file_type=extension.lstrip("."),
                    file_size=file_size,
                    page_count=page_count,
                )
            else:
                # Use MarkItDown for other formats
                result = self._converter.convert(str(temp_path))
                text_content = result.text_content
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
