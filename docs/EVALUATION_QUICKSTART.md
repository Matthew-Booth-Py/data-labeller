# Evaluation System Quick Start Guide

## 5-Minute Setup

### Step 1: Prepare Your Documents (2 min)

1. Upload 20-30 documents of the same type (e.g., invoices)
2. Classify them all as the same document type
3. Define schema fields for that document type:
   ```json
   {
     "fields": [
       {"name": "invoice_number", "type": "string", "required": true},
       {"name": "total_amount", "type": "number", "required": true},
       {"name": "invoice_date", "type": "date", "required": true},
       {"name": "vendor_name", "type": "string", "required": true}
     ]
   }
   ```

### Step 2: Create Ground Truth (2 min)

1. Open each document in the Data Labeller
2. Annotate the key fields:
   - Highlight "INV-12345" → Label as `invoice_number`
   - Highlight "$1,500.00" → Label as `total_amount`
   - Highlight "2024-01-15" → Label as `invoice_date`
   - Highlight "Acme Corp" → Label as `vendor_name`
3. Save annotations

### Step 3: Run Your First Evaluation (1 min)

```bash
# Using curl
curl -X POST http://localhost:8000/api/evaluation/run \
  -H "Content-Type: application/json" \
  -d '{
    "document_id": "your-document-id",
    "use_llm_refinement": true
  }'

# Or using the UI
# Navigate to /evaluation → Click "Run Evaluation" → Select document
```

### Step 4: View Results

Check the evaluation dashboard at `/evaluation` to see:
- **F1 Score**: Overall extraction quality (aim for > 0.85)
- **Precision**: How many extracted values are correct
- **Recall**: How many ground truth values were found
- **Field-level breakdown**: Which fields need improvement

## Example Workflow

### Scenario: Improving Invoice Extraction

#### Iteration 1: Baseline
```python
# Create baseline prompt version
POST /api/evaluation/prompts
{
  "name": "v1.0-baseline",
  "system_prompt": "Extract invoice fields from the document.",
  "is_active": true
}

# Run evaluation
POST /api/evaluation/run
{
  "document_id": "invoice-001",
  "prompt_version_id": "v1.0-baseline"
}

# Results:
# F1: 0.72, Accuracy: 0.70
# Problem: Date field has 0.50 recall (missing 50% of dates)
```

#### Iteration 2: Improved Date Handling
```python
# Create improved prompt version
POST /api/evaluation/prompts
{
  "name": "v2.0-better-dates",
  "system_prompt": """Extract invoice fields from the document.

For dates:
- Accept formats: MM/DD/YYYY, DD-MM-YYYY, YYYY-MM-DD
- Normalize to ISO format: YYYY-MM-DD
- Look for keywords: "Date:", "Invoice Date:", "Dated:"
""",
  "is_active": true
}

# Run evaluation with new prompt
POST /api/evaluation/run
{
  "document_id": "invoice-001",
  "prompt_version_id": "v2.0-better-dates"
}

# Results:
# F1: 0.88, Accuracy: 0.85
# Date recall improved: 0.50 → 0.92
```

#### Iteration 3: Compare & Deploy
```python
# Compare prompt versions
GET /api/evaluation/compare/prompts?document_type_id=invoice

# Response shows v2.0 is better:
# v2.0: F1=0.88, v1.0: F1=0.72

# Activate v2.0 as production prompt
PATCH /api/evaluation/prompts/v2.0-better-dates
{
  "is_active": true
}
```

## Common Patterns

### Pattern 1: Field-Specific Improvements

**Problem**: One field has low accuracy

**Solution**:
1. Look at field-level metrics to identify the problem field
2. Review failed extractions for that field
3. Add field-specific instructions to the prompt
4. Re-evaluate

**Example**:
```python
# Before: "Extract the total amount"
# After: "Extract the total amount. Look for keywords: 
#         'Total:', 'Amount Due:', 'Balance:'. 
#         Include currency symbol. Format: $X,XXX.XX"
```

### Pattern 2: Format Normalization

**Problem**: Values are extracted but in wrong format

**Solution**:
1. Add normalization instructions to prompt
2. Use post-processing to standardize format

**Example**:
```python
# Dates: Always output as YYYY-MM-DD
# Amounts: Always output as float without currency symbol
# Phone numbers: Always output as +1-XXX-XXX-XXXX
```

### Pattern 3: Context-Aware Extraction

**Problem**: Multiple similar values, extracting wrong one

**Solution**:
1. Add context clues to prompt
2. Specify location hints (e.g., "in the header", "near the bottom")

**Example**:
```python
# Before: "Extract the date"
# After: "Extract the invoice date (usually in the header, 
#         near the invoice number, not the due date)"
```

## Metrics Interpretation

### F1 Score
- **> 0.90**: Excellent - production ready
- **0.80-0.90**: Good - minor improvements needed
- **0.70-0.80**: Fair - needs work on specific fields
- **< 0.70**: Poor - major prompt revision needed

### Precision vs Recall
- **High Precision, Low Recall**: Extractions are correct but missing many fields
  - Fix: Make prompt more aggressive, look for more patterns
- **Low Precision, High Recall**: Finding fields but many are wrong
  - Fix: Add validation rules, be more specific about what to extract
- **Both Low**: Prompt needs major revision

### Field-Level Analysis
- Focus on fields with lowest scores first
- One field can drag down overall F1 significantly
- Sometimes it's better to skip a hard field than extract it incorrectly

## Tips & Tricks

### Tip 1: Start Simple
Don't try to extract 20 fields at once. Start with 3-5 critical fields, get them to 0.90+ F1, then add more.

### Tip 2: Use Examples
Include 1-2 examples in your prompt showing the exact format you want.

### Tip 3: Iterate Quickly
Make small changes, test immediately. Don't spend hours crafting the perfect prompt without testing.

### Tip 4: Track Everything
Keep a log of what you changed and why. Future you will thank you.

### Tip 5: Validate Ground Truth
If a field consistently fails, check if your ground truth annotations are correct.

## Troubleshooting

### "No evaluations found"
- Make sure document is classified (has document type)
- Make sure document has annotations (ground truth)
- Check that schema fields are defined for the document type

### "Evaluation failed: Document not found"
- Verify document ID is correct
- Check that document exists in vector store

### "All metrics are 0.0"
- Check if annotations match schema field names
- Verify that label names map to field names (e.g., label "invoice_number" → field "invoice_number")

### "F1 is low but extractions look correct"
- Check for whitespace differences (e.g., "INV-123" vs "INV-123 ")
- Check for case sensitivity (e.g., "Acme Corp" vs "ACME CORP")
- Values are normalized before comparison, but check edge cases

## Next Steps

1. **Set up monitoring**: Run weekly evaluations on random samples
2. **Create more prompt versions**: Test different approaches
3. **Expand to more document types**: Apply learnings to other types
4. **Automate**: Integrate evaluation into your CI/CD pipeline
5. **Share results**: Export metrics to share with team

## Resources

- [Full Evaluation System Documentation](./EVALUATION_SYSTEM.md)
- [API Reference](./API.md)
- [Prompt Engineering Guide](./PROMPT_ENGINEERING.md)
