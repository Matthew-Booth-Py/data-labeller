"""Test PDF table extraction with pdfplumber.

Tests two extraction modes:
1. Bordered tables -> Converted to markdown format
2. Financial tables (no borders) -> Layout-preserving text extraction
"""

import tempfile
from pathlib import Path

import pdfplumber
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet


def create_test_pdf_with_bordered_table() -> str:
    """Create a test PDF with a bordered financial table."""
    temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    temp_path = temp_file.name
    temp_file.close()

    doc = SimpleDocTemplate(temp_path, pagesize=letter)
    styles = getSampleStyleSheet()
    elements = []

    elements.append(Paragraph("Intel Corporation - Q4 2025 Results", styles["Heading1"]))
    elements.append(Paragraph("Consolidated Statements", styles["Heading2"]))

    data = [
        ["(In Millions)", "Dec 27, 2025", "Dec 28, 2024", "Dec 27, 2025", "Dec 28, 2024"],
        ["Net revenue", "$13,674", "$14,260", "$52,853", "$53,101"],
        ["Cost of sales", "8,731", "8,676", "34,478", "35,756"],
        ["Gross profit", "4,943", "5,584", "18,375", "17,345"],
        ["R&D", "3,219", "3,876", "13,774", "16,546"],
        ["Operating expenses", "4,363", "5,172", "20,589", "29,023"],
        ["Operating income", "580", "412", "(2,214)", "(11,678)"],
    ]

    table = Table(data)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black),
    ]))
    elements.append(table)

    doc.build(elements)
    return temp_path


def table_to_markdown(table: list[list[str | None]]) -> str:
    """Convert a table (list of rows) to markdown format."""
    if not table or len(table) == 0:
        return ""

    cleaned = []
    for row in table:
        cleaned.append([str(cell).strip().replace("\n", " ") if cell else "" for cell in row])

    if len(cleaned) == 0:
        return ""

    col_count = max(len(row) for row in cleaned)

    for row in cleaned:
        while len(row) < col_count:
            row.append("")

    lines = []
    header = cleaned[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("| " + " | ".join(["---"] * col_count) + " |")

    for row in cleaned[1:]:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def extract_pdf_with_tables(pdf_path: str, verbose: bool = False) -> tuple[str, int]:
    """
    Extract text and tables from PDF using pdfplumber.
    
    Uses layout-preserving extraction for financial tables without borders.
    Bordered tables are converted to markdown format.
    """
    content_parts = []
    page_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)
        if verbose:
            print(f"\n=== PDF has {page_count} pages ===\n")

        for page_num, page in enumerate(pdf.pages, 1):
            if verbose:
                print(f"\n--- Processing Page {page_num} ---")

            page_content = []

            # Try to extract bordered tables first (using lines detection)
            table_settings = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
            }
            bordered_tables = page.extract_tables(table_settings)
            has_bordered_tables = bordered_tables and any(len(t) > 1 for t in bordered_tables if t)

            if verbose:
                print(f"Found {len(bordered_tables) if bordered_tables else 0} bordered tables")

            if has_bordered_tables:
                # Found bordered tables - convert to markdown
                page_content.append(f"\n## Page {page_num}\n")

                for i, table in enumerate(bordered_tables):
                    if table and len(table) > 1:
                        md_table = table_to_markdown(table)
                        if md_table:
                            page_content.append(f"\n### Table {i+1}\n\n{md_table}\n")
                            if verbose:
                                print(f"Converted table {i+1} to markdown")

                # Also get text outside tables
                text = page.extract_text() or ""
                if text.strip():
                    page_content.append(f"\n{text}\n")
            else:
                # No bordered tables - use layout-preserving text extraction
                # This preserves whitespace alignment for financial tables
                text = page.extract_text(
                    layout=True,
                    x_tolerance=2,
                    y_tolerance=2,
                ) or ""

                if text.strip():
                    if page_count > 1:
                        page_content.append(f"\n--- Page {page_num} ---\n")
                    page_content.append(text)
                    if verbose:
                        print("Used layout-preserving extraction")

            if page_content:
                content_parts.append("\n".join(page_content))

    return "\n\n".join(content_parts), page_count


def test_bordered_table_extraction():
    """Test that bordered tables are properly extracted and converted to markdown."""
    print("Creating test PDF with bordered table...")
    pdf_path = create_test_pdf_with_bordered_table()
    print(f"Created: {pdf_path}")

    try:
        content, page_count = extract_pdf_with_tables(pdf_path, verbose=True)

        print("\n" + "=" * 60)
        print("EXTRACTED CONTENT:")
        print("=" * 60)
        print(content)
        print("=" * 60)

        # Verify markdown table format
        assert "|" in content, "Markdown table pipe characters should be present"
        assert "---" in content, "Markdown table separator should be present"
        assert "Net revenue" in content, "Table content should be preserved"
        assert "13,674" in content, "Numeric values should be preserved"

        print("\n✓ Bordered table test passed!")
        return True

    finally:
        Path(pdf_path).unlink(missing_ok=True)


def test_layout_preservation(pdf_path: str):
    """Test that financial tables preserve column alignment through spacing."""
    if not Path(pdf_path).exists():
        print(f"File not found: {pdf_path}")
        return False

    print(f"\nTesting layout preservation on: {pdf_path}")
    content, page_count = extract_pdf_with_tables(pdf_path, verbose=True)

    print("\n" + "=" * 60)
    print(f"EXTRACTED CONTENT PREVIEW ({page_count} pages, {len(content)} chars):")
    print("=" * 60)
    print(content[:2500])
    
    # Find page 9 content (financial tables)
    page9_marker = content.find("Page 9")
    if page9_marker > 0:
        print("\n" + "=" * 60)
        print("PAGE 9 FINANCIAL TABLES:")
        print("=" * 60)
        page9_content = content[page9_marker:page9_marker+2500]
        print(page9_content)
        
        # Verify layout preservation
        # Financial tables should have multiple spaces between columns
        has_alignment = "  " in page9_content  # Multiple spaces = column alignment
        has_revenue = "Revenue" in page9_content
        has_numbers = any(char.isdigit() for char in page9_content) #
        
        print("\n" + "=" * 60)
        print("VALIDATION:")
        print(f"  - Column alignment (spaces): {'✓' if has_alignment else '✗'}")
        print(f"  - Contains 'Revenue': {'✓' if has_revenue else '✗'}")
        print(f"  - Contains numbers: {'✓' if has_numbers else '✗'}")
        
        if has_alignment and has_revenue and has_numbers:
            print("\n✓ Layout preservation test passed!")
            return True
        else:
            print("\n✗ Layout preservation test failed")
            return False
    else:
        print("Page 9 not found in content")
        return False


if __name__ == "__main__":
    import sys

    print("=" * 60)
    print("PDF TABLE EXTRACTION TESTS")
    print("=" * 60) to 

    # Test 1: Bordered tables -> markdown
    print("\n" + "=" * 60)
    print("TEST 1: Bordered Table -> Markdown Conversion")
    print("=" * 60)
    test_bordered_table_extraction()

    # Test 2: Real PDF with layout preservation
    if len(sys.argv) > 1:
        print("\n" + "=" * 60)
        print("TEST 2: Layout Preservation for Financial Tables")
        print("=" * 60)
        test_layout_preservation(sys.argv[1])
    else:
        print("\n(Skipping real PDF test - no file path provided)")
