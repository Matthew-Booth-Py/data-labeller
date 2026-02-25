"""Test PDF table extraction with different strategies."""

import pdfplumber


def extract_with_settings(pdf_path: str) -> None:
    """Try different table extraction strategies."""

    with pdfplumber.open(pdf_path) as pdf:
        print(f"PDF has {len(pdf.pages)} pages\n")

        # Focus on page 3 which should have the financial statement
        for page_num in [3, 4, 5, 9]:  # Try specific pages
            if page_num > len(pdf.pages):
                continue

            page = pdf.pages[page_num - 1]
            print(f"\n{'='*60}")
            print(f"PAGE {page_num}")
            print(f"{'='*60}")

            # Strategy 1: Default table detection
            tables = page.extract_tables()
            print(f"\n1. Default extract_tables(): {len(tables)} tables found")

            # Strategy 2: More aggressive settings
            table_settings = {
                "vertical_strategy": "text",
                "horizontal_strategy": "text",
                "snap_tolerance": 5,
                "join_tolerance": 5,
                "edge_min_length": 10,
                "min_words_vertical": 2,
                "min_words_horizontal": 2,
            }
            tables2 = page.extract_tables(table_settings)
            print(f"2. Text-based strategy: {len(tables2)} tables found")

            # Strategy 3: Lines only (for bordered tables)
            table_settings3 = {
                "vertical_strategy": "lines",
                "horizontal_strategy": "lines",
            }
            tables3 = page.extract_tables(table_settings3)
            print(f"3. Lines-only strategy: {len(tables3)} tables found")

            # Strategy 4: Explicit table finding
            found_tables = page.find_tables()
            print(f"4. find_tables(): {len(found_tables)} tables found")

            # Show first table if found with strategy 2
            if tables2:
                print("\nTable from strategy 2 (first 5 rows):")
                for row in tables2[0][:5]:
                    print(f"  {row}")

            # Also show raw text to understand structure
            text = page.extract_text()
            print("\nRaw text preview (first 1000 chars):")
            print(text[:1000] if text else "No text")


def try_explicit_extraction(pdf_path: str) -> None:
    """Try explicit word-based extraction for financial tables."""

    with pdfplumber.open(pdf_path) as pdf:
        # Page 3 should have the consolidated statement
        page = pdf.pages[2]  # 0-indexed, so page 3

        print("\n" + "=" * 60)
        print("EXPLICIT WORD EXTRACTION - Page 3")
        print("=" * 60)

        # Get all words with positions
        words = page.extract_words(
            x_tolerance=3,
            y_tolerance=3,
            keep_blank_chars=True,
            extra_attrs=["top", "bottom", "x0", "x1"],
        )

        # Group words by their vertical position (rows)
        rows = {}
        for word in words:
            # Round top position to group words on same line
            row_key = round(word["top"] / 5) * 5
            if row_key not in rows:
                rows[row_key] = []
            rows[row_key].append(word)

        # Sort rows by position and words within rows by x position
        sorted_rows = sorted(rows.items())

        print(f"\nFound {len(sorted_rows)} text rows\n")

        # Print rows that look like table data (multiple columns)
        for row_pos, words_in_row in sorted_rows[:30]:  # First 30 rows
            words_in_row.sort(key=lambda w: w["x0"])
            text_parts = [w["text"] for w in words_in_row]
            line = " | ".join(text_parts)
            if len(words_in_row) > 3:  # Likely table row if many columns
                print(f"[TABLE?] {line[:120]}")
            else:
                print(f"         {line[:120]}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python test_pdf_tables_v2.py <pdf_path>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    print("Testing different extraction strategies...\n")
    extract_with_settings(pdf_path)

    print("\n\n")
    try_explicit_extraction(pdf_path)
