"""Test layout-preserving PDF extraction."""

import sys

import pdfplumber


def table_to_markdown(table: list[list[str | None]]) -> str:
    """Convert table to markdown format."""
    if not table or len(table) == 0:
        return ""

    # Clean and normalize cells
    def clean_cell(cell) -> str:
        if cell is None:
            return ""
        text = str(cell).strip()
        text = text.replace("\n", " ").replace("|", "\\|")
        return text

    rows = [[clean_cell(cell) for cell in row] for row in table]
    if not rows or not rows[0]:
        return ""

    num_cols = max(len(row) for row in rows)
    rows = [row + [""] * (num_cols - len(row)) for row in rows]

    header = rows[0]
    md_lines = []
    md_lines.append("| " + " | ".join(header) + " |")
    md_lines.append("| " + " | ".join(["---"] * num_cols) + " |")

    for row in rows[1:]:
        md_lines.append("| " + " | ".join(row) + " |")

    return "\n".join(md_lines)


def extract_pdf_with_layout(pdf_path: str) -> tuple[str, int]:
    """Extract with layout preservation."""
    content_parts = []
    page_count = 0

    with pdfplumber.open(pdf_path) as pdf:
        page_count = len(pdf.pages)

        for page_num, page in enumerate(pdf.pages, 1):
            page_content = []

            # Try bordered tables first
            table_settings = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
            }
            bordered_tables = page.extract_tables(table_settings)

            if bordered_tables and any(len(t) > 1 for t in bordered_tables if t):
                page_content.append(f"\n## Page {page_num}\n")
                for table in bordered_tables:
                    if table and len(table) > 1:
                        md_table = table_to_markdown(table)
                        if md_table:
                            page_content.append(f"\n{md_table}\n")

                text = page.extract_text() or ""
                if text.strip():
                    page_content.append(f"\n{text}\n")
            else:
                # Use layout-preserving extraction
                text = (
                    page.extract_text(
                        layout=True,
                        x_tolerance=2,
                        y_tolerance=2,
                    )
                    or ""
                )

                if text.strip():
                    if page_count > 1:
                        page_content.append(f"\n--- Page {page_num} ---\n")
                    page_content.append(text)

            if page_content:
                content_parts.append("\n".join(page_content))

    return "\n\n".join(content_parts), page_count


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_layout_extraction.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    print(f"Extracting from: {pdf_path}\n")

    content, pages = extract_pdf_with_layout(pdf_path)

    print(f"Total pages: {pages}")
    print("=" * 80)

    # Show first 5000 chars or so
    print(content[:5000])

    if len(content) > 5000:
        print("\n... (truncated) ...\n")

    # Also show page 9 specifically (financial tables)
    print("\n" + "=" * 80)
    print("PAGE 9 CONTENT (FINANCIAL TABLES):")
    print("=" * 80)

    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) >= 9:
            page9 = pdf.pages[8]  # 0-indexed
            text = page9.extract_text(layout=True, x_tolerance=2, y_tolerance=2)
            print(text if text else "No content")
