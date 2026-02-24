# Retrieval Query Simplification - Implementation Complete

## Summary

Successfully simplified the retrieval query generation to improve page matching accuracy for entity extraction.

## Problem Identified

The `_build_field_query` method was building overly complex queries by concatenating:
- Field name (semantic ✅)
- Visual features (layout instructions like "Two labeled column groups") ❌
- Visual guidance (extraction procedures like "Parse the leftmost column") ❌
- Extraction prompt (200+ chars of HOW-TO instructions) ❌

This created queries that didn't match the semantic content in page summaries.

### Example - Before:
```
quarterly melted metrics Two labeled column groups: 'GAAP' and 'Non-GAAP', each with three sub-columns Leftmost vertical list of metric labels (e.g., Revenue ($B), Gross margin) Numeric values often colored blue and negative numbers shown in parentheses Change columns use textual qualifiers: 'up'/'down' and include 'ppts' for percentage points Column headers aligned horizontally above their numeric columns, visually separated by thin horizontal rules table column row Parse the leftmost column as the metric key. For each metric row, extract three GAAP fields and three Non-GAAP fields using the sub-column headers as keys (Q3 2025, Q3 2024, vs. Q3 2024). Trim whitespace and preserve signs: treat values in parentheses as negative...
```

## Solution Implemented

Modified [`backend/src/uu_backend/services/extraction_service.py`](backend/src/uu_backend/services/extraction_service.py) to use only semantic content:

```python
def _build_field_query(self, field: SchemaField) -> str:
    """Build a search query for a schema field.
    
    Uses only semantic content (field name + description) to match
    page summaries, avoiding extraction instructions.
    """
    parts = [field.name.replace("_", " ")]
    
    if field.description:
        parts.append(field.description)
    
    query = " ".join(parts)
    logger.info(f"Retrieval query for field '{field.name}': {query}")
    return query
```

### Example - After:
```
quarterly melted metrics Melted quarterly financial metrics where each row is metric, period, and raw extracted value
```

## Results

### Test Document: `intc 8k.pdf` (ID: `353c084a-70ac-4a89-8eb2-31215806edf9`)

**Field:** `quarterly_melted_metrics`

**Before:**
- Likely matched Page 14 (definitions table) or other non-relevant pages
- Query was too specific with visual/extraction instructions

**After:**
- ✅ **Correctly matches Page 4** (the actual financial results table)
- Query: `quarterly melted metrics Melted quarterly financial metrics where each row is metric, period, and raw extracted value`
- Top result score: 0.032
- Page 4 summary: "Intel's Oct 23, 2025 news release reporting Q3 2025 financial results: revenue $13.7B (up 3% YoY), GAAP EPS $0.90 and non-GAAP EPS $0.23..."

### Logs Verification

```
🔍 Field: quarterly_melted_metrics → Query: quarterly melted metrics Melted quarterly financial metrics where each row is metric, period, and raw extracted value
  quarterly_melted_metrics: pages [4]
```

## Benefits

1. **Improved Accuracy**: Queries now match semantic content in page summaries
2. **Simpler Queries**: Easier to understand and debug
3. **Better Performance**: Semantic matching works better than keyword stuffing
4. **Maintainability**: Clear separation between search (semantic) and extraction (procedural)

## Files Modified

- [`backend/src/uu_backend/services/extraction_service.py`](backend/src/uu_backend/services/extraction_service.py) - Lines 546-580

## Deployment

Changes deployed via Docker rebuild:
```bash
docker-compose build backend
docker-compose up -d backend
```

## Testing

Verified through:
1. Manual query testing via Django shell
2. API extraction endpoint (`/api/v1/documents/{id}/extract`)
3. Log verification showing correct page matching
4. End-to-end test with "Suggest labels" feature

---

**Date:** 2026-02-13
**Status:** ✅ Complete and Verified
