# Quick Start: Structured Output & Schema-Based Labeling

## TL;DR

Your schema fields now automatically:
1. ✅ Generate Pydantic models for type-safe extraction
2. ✅ Create labels for annotation
3. ✅ Suggest annotations with AI (fast ground truth)
4. ✅ Enable direct extraction without annotations

**No changes needed to existing schemas!** Everything is backward compatible.

## 30-Second Test

```powershell
# 1. Classify document (if not already done)
$docId = "2ac28822-3731-45da-aede-221561bfcb1a"
$typeId = "your-claim-form-type-id"

Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/taxonomy/documents/$docId/classify" `
  -Method POST `
  -ContentType "application/json" `
  -Body (@{document_type_id=$typeId} | ConvertTo-Json)

# 2. Get AI-suggested annotations (creates ground truth)
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/documents/$docId/suggest-annotations?auto_accept=true" `
  -Method POST

# 3. Run evaluation with structured output
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/evaluation/run" `
  -Method POST `
  -ContentType "application/json" `
  -Body (@{
    document_id=$docId
    use_structured_output=$true
  } | ConvertTo-Json)
```

Done! You now have:
- Ground truth annotations
- Extraction results
- Evaluation metrics

## Two New Features

### Feature 1: Direct Extraction (No Annotations)

Extract data directly using your schema, bypassing the annotation step entirely.

```powershell
# Extract using structured output
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/taxonomy/documents/$docId/extract?use_structured_output=true" `
  -Method POST
```

**Returns:**
```json
{
  "document_id": "...",
  "fields": [
    {
      "field_name": "claim_items",
      "value": [
        {
          "item_name": "Laptop Repair",
          "item_description": "Screen replacement",
          "item_cost": 450.00
        }
      ],
      "confidence": 0.95
    }
  ]
}
```

### Feature 2: AI-Suggested Annotations (Fast Labeling)

Let the LLM suggest where to annotate based on your schema.

```powershell
# Get suggestions (review first)
$suggestions = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/documents/$docId/suggest-annotations" `
  -Method POST

# Or auto-accept (fast ground truth)
Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/documents/$docId/suggest-annotations?auto_accept=true" `
  -Method POST
```

**Returns:**
```json
{
  "suggestions": [
    {
      "field_name": "claim_items",
      "label_name": "claim_items_item_name",
      "spans": [
        {
          "text": "Laptop Repair",
          "start_char": 120,
          "end_char": 133
        }
      ],
      "confidence": 0.85
    }
  ],
  "extraction_preview": {
    "claim_items": [...]
  }
}
```

## When to Use What

### Use Direct Extraction When:
- ✅ You just want to extract data (no evaluation needed)
- ✅ You trust the LLM's extraction quality
- ✅ You want fast results without labeling

### Use Annotation Suggestions When:
- ✅ You need ground truth for evaluation
- ✅ You want to build a labeled dataset quickly
- ✅ You want to compare different prompts/models

### Use Traditional Annotation When:
- ✅ You need very precise ground truth
- ✅ You're training ML models
- ✅ You have complex edge cases

## Complete Workflow Example

### Goal: Evaluate extraction quality on 10 claim forms

```powershell
# Step 1: Get your document type ID
$types = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/taxonomy/types"
$claimFormType = $types | Where-Object { $_.name -eq "Claim Form" }
$typeId = $claimFormType.id

# Step 2: Get your documents
$docs = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/documents"
$claimDocs = $docs.documents | Select-Object -First 10

# Step 3: Process each document
foreach ($doc in $claimDocs) {
    Write-Host "Processing $($doc.filename)..."

    # Classify
    Invoke-RestMethod `
      -Uri "http://localhost:8000/api/v1/taxonomy/documents/$($doc.id)/classify" `
      -Method POST `
      -ContentType "application/json" `
      -Body (@{document_type_id=$typeId} | ConvertTo-Json)

    # Create ground truth (auto-accept suggestions)
    Invoke-RestMethod `
      -Uri "http://localhost:8000/api/v1/documents/$($doc.id)/suggest-annotations?auto_accept=true" `
      -Method POST

    # Run evaluation
    $eval = Invoke-RestMethod `
      -Uri "http://localhost:8000/api/v1/evaluation/run" `
      -Method POST `
      -ContentType "application/json" `
      -Body (@{
        document_id=$doc.id
        use_structured_output=$true
      } | ConvertTo-Json)

    Write-Host "F1 Score: $($eval.evaluation.metrics.aggregate_metrics.f1_score)"
}

# Step 4: View aggregate results
$summary = Invoke-RestMethod -Uri "http://localhost:8000/api/v1/evaluation/summary?document_type_id=$typeId"
Write-Host "Average F1: $($summary.average_f1_score)"
```

## Comparing Extraction Methods

```powershell
$docId = "your-doc-id"

# Method 1: Annotation-based (old way)
$eval1 = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/evaluation/run" `
  -Method POST `
  -ContentType "application/json" `
  -Body (@{
    document_id=$docId
    use_structured_output=$false
    use_llm_refinement=$true
  } | ConvertTo-Json)

# Method 2: Structured output (new way)
$eval2 = Invoke-RestMethod `
  -Uri "http://localhost:8000/api/v1/evaluation/run" `
  -Method POST `
  -ContentType "application/json" `
  -Body (@{
    document_id=$docId
    use_structured_output=$true
  } | ConvertTo-Json)

# Compare
Write-Host "Annotation-based F1: $($eval1.evaluation.metrics.aggregate_metrics.f1_score)"
Write-Host "Structured output F1: $($eval2.evaluation.metrics.aggregate_metrics.f1_score)"
```

## Tips

1. **Start with auto-accept** for quick iteration
   - Then spot-check a few documents manually
   - Correct any errors in the UI

2. **Use structured output for evaluation** to match the suggestion approach
   - Both use the same Pydantic model generation
   - Results will be more consistent

3. **Define good field descriptions** in your schema
   - The LLM uses these to understand what to extract
   - Better descriptions = better suggestions

4. **For tables**, labels are auto-created as `field_name_property_name`
   - Example: `claim_items_item_cost`
   - This matches the evaluation expectations

## Troubleshooting

**Error: "Document is not classified"**
```powershell
# Classify first
POST /api/v1/taxonomy/documents/{id}/classify
{
  "document_type_id": "your-type-id"
}
```

**Error: "Document type has no schema fields"**
- Your document type needs schema fields defined
- Check: `GET /api/v1/taxonomy/types/{type_id}`

**No suggestions returned**
- Verify labels exist: `GET /api/v1/annotations/labels?document_type_id={type_id}`
- Labels should be auto-created from schema
- If not, rebuild backend: `docker compose build backend && docker compose up -d`

**Incorrect text spans**
- The LLM does its best but may not be perfect
- Use `auto_accept=false` to review first
- Correct in the UI as needed

## Next Steps

1. Read `SCHEMA_BASED_LABELING.md` for detailed workflow
2. Read `STRUCTURED_OUTPUT_SUMMARY.md` for technical details
3. Try it with your claim form document
4. Build a batch processing script for multiple documents
5. Compare evaluation results between methods
