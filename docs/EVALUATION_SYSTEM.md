# Extraction Evaluation System

## Overview

The Extraction Evaluation System provides a data-driven approach to measuring and improving extraction quality by comparing automated extraction results against ground truth annotations.

## Core Capabilities

### 1. Document Classification
- Automatically classify documents by type (e.g., Invoice, Claim Form, Contract)
- LLM-based classification with confidence scores
- Manual override capability

### 2. Form Extraction via Schema
- Extract specific fields from documents based on document type
- Use schema definitions + LLM to extract structured data
- Output: JSON with field values (e.g., `{"invoice_number": "INV-12345", "total": 1500}`)

### 3. Data Labeller Tool (AI-Accelerated)
- Manual annotation tool with AI suggestions
- Creates validation datasets for evaluation
- Human labels text spans, AI suggests labels, feedback loop trains ML model

## The Evaluation Feedback Loop

```
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  1. Data Labeller → Creates Ground Truth Annotations       │
│                                                             │
│  2. Form Extraction → Runs Automated Extraction            │
│                                                             │
│  3. Evaluation → Compares Extraction vs Ground Truth       │
│                                                             │
│  4. Metrics → Calculate F1, Precision, Recall              │
│                                                             │
│  5. Iteration → Tweak Prompts, Re-evaluate                 │
│                                                             │
│  6. Monitoring → Track Performance Over Time               │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Key Features

### Prompt Versioning
- Track different versions of extraction prompts
- Compare performance across prompt iterations
- A/B test prompt changes with real metrics
- Activate/deactivate prompt versions

### Evaluation Metrics
- **Accuracy**: Correct fields / Total fields
- **Precision**: Correct / (Correct + Incorrect + Extra)
- **Recall**: Correct / (Correct + Incorrect + Missing)
- **F1 Score**: Harmonic mean of precision and recall
- **Field-level metrics**: Per-field accuracy breakdown

### Evaluation History
- Store all evaluation runs with timestamps
- Track extraction time performance
- Link evaluations to specific prompt versions
- Aggregate metrics across document sets

## API Endpoints

### Run Evaluation
```http
POST /api/evaluation/run
Content-Type: application/json

{
  "document_id": "doc-123",
  "prompt_version_id": "pv-456",  // optional, null = active version
  "use_llm_refinement": true,
  "evaluated_by": "user@example.com",
  "notes": "Testing new date extraction prompt"
}
```

**Response:**
```json
{
  "evaluation": {
    "id": "eval-789",
    "document_id": "doc-123",
    "document_type_id": "invoice",
    "prompt_version_id": "pv-456",
    "prompt_version_name": "v2.0-improved-dates",
    "metrics": {
      "total_fields": 10,
      "correct_fields": 8,
      "incorrect_fields": 1,
      "missing_fields": 1,
      "extra_fields": 0,
      "accuracy": 0.8,
      "precision": 0.89,
      "recall": 0.89,
      "f1_score": 0.89,
      "field_evaluations": [
        {
          "field_name": "invoice_number",
          "extracted_value": "INV-12345",
          "ground_truth_value": "INV-12345",
          "is_correct": true,
          "is_present": true,
          "is_extracted": true
        },
        // ... more fields
      ]
    },
    "extraction_time_ms": 1250,
    "evaluated_at": "2024-01-15T10:30:00Z",
    "notes": "Testing new date extraction prompt"
  }
}
```

### Get Evaluation Summary
```http
GET /api/evaluation/summary/aggregate?prompt_version_id=pv-456&document_type_id=invoice
```

**Response:**
```json
{
  "summary": {
    "prompt_version_id": "pv-456",
    "prompt_version_name": "v2.0-improved-dates",
    "document_type_id": "invoice",
    "total_evaluations": 25,
    "avg_accuracy": 0.85,
    "avg_precision": 0.88,
    "avg_recall": 0.86,
    "avg_f1_score": 0.87,
    "field_performance": {
      "invoice_number": {
        "accuracy": 0.96,
        "precision": 0.98,
        "recall": 0.96
      },
      "total_amount": {
        "accuracy": 0.88,
        "precision": 0.90,
        "recall": 0.88
      },
      "date": {
        "accuracy": 0.75,
        "precision": 0.80,
        "recall": 0.75
      }
    },
    "earliest_evaluation": "2024-01-10T09:00:00Z",
    "latest_evaluation": "2024-01-15T16:30:00Z"
  }
}
```

### Compare Prompt Versions
```http
GET /api/evaluation/compare/prompts?document_type_id=invoice
```

**Response:**
```json
{
  "comparisons": [
    {
      "prompt_version_id": "pv-456",
      "prompt_version_name": "v2.0-improved-dates",
      "total_evaluations": 25,
      "avg_f1_score": 0.87,
      "avg_accuracy": 0.85
    },
    {
      "prompt_version_id": "pv-123",
      "prompt_version_name": "v1.0-baseline",
      "total_evaluations": 30,
      "avg_f1_score": 0.78,
      "avg_accuracy": 0.76
    }
  ],
  "document_type_id": "invoice"
}
```

### Prompt Version Management

#### Create Prompt Version
```http
POST /api/evaluation/prompts
Content-Type: application/json

{
  "name": "v2.0-improved-dates",
  "document_type_id": "invoice",
  "system_prompt": "You are a document extraction expert...",
  "user_prompt_template": "Extract fields: {schema_desc}\n\nDocument: {content}",
  "description": "Improved date parsing with ISO format normalization",
  "is_active": true,
  "created_by": "user@example.com"
}
```

#### Get Active Prompt Version
```http
GET /api/evaluation/prompts/active/current?document_type_id=invoice
```

#### List Prompt Versions
```http
GET /api/evaluation/prompts?document_type_id=invoice&is_active=true
```

## Workflow

### 1. Create Ground Truth Dataset
1. Upload documents to the system
2. Classify documents by type
3. Use the Data Labeller tool to annotate key fields
4. Mark documents as "validation set"

### 2. Run Initial Evaluation
1. Create a baseline prompt version (v1.0)
2. Run evaluation on validation set
3. Review metrics and identify weak fields

### 3. Iterate on Prompts
1. Create new prompt version (v2.0) with improvements
2. Run evaluation with new prompt
3. Compare metrics against baseline
4. Activate better-performing prompt

### 4. Continuous Monitoring
1. Set up automated evaluation on new documents
2. Track metrics over time in dashboard
3. Get alerts when accuracy drops
4. Re-label documents that fail evaluation

## Database Schema

### `prompt_versions` Table
```sql
CREATE TABLE prompt_versions (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    document_type_id TEXT,
    system_prompt TEXT NOT NULL,
    user_prompt_template TEXT,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 0,
    created_by TEXT,
    created_at TEXT NOT NULL
);
```

### `evaluations` Table
```sql
CREATE TABLE evaluations (
    id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    document_type_id TEXT NOT NULL,
    prompt_version_id TEXT,
    metrics TEXT NOT NULL,  -- JSON
    extraction_time_ms INTEGER,
    evaluated_by TEXT,
    evaluated_at TEXT NOT NULL,
    notes TEXT
);
```

## Frontend Components

### Evaluation Dashboard (`/evaluation`)
- Summary cards showing aggregate metrics
- Field-level performance breakdown
- Recent evaluations table
- Prompt version filter

### Prompt Comparison View (`/evaluation/compare`)
- Side-by-side comparison of prompt versions
- Performance trends over time
- Field-level comparison charts

### Per-Document Evaluation View
- Show extracted values vs ground truth
- Highlight mismatches (false positives/negatives)
- Allow re-labeling if ground truth was wrong

## Best Practices

### Creating Ground Truth
- Label at least 20-30 documents per document type
- Ensure diverse document variations (different formats, dates, amounts)
- Have multiple annotators for inter-annotator agreement
- Review and correct annotation errors

### Prompt Engineering
- Start with a simple baseline prompt
- Make one change at a time
- Test on validation set before deploying
- Document what changed in each version

### Evaluation Strategy
- Run evaluation after every prompt change
- Track metrics in a spreadsheet or dashboard
- Set minimum acceptable thresholds (e.g., F1 > 0.85)
- Re-evaluate periodically as documents change

### Monitoring
- Set up weekly evaluation runs on random samples
- Alert when F1 drops below threshold
- Investigate field-level degradation
- Re-train or update prompts as needed

## Example Use Case

### Problem
Invoice extraction is failing to correctly extract dates 30% of the time.

### Solution
1. **Analyze**: Review field-level metrics, see that `invoice_date` has 0.70 recall
2. **Investigate**: Look at failed extractions, notice dates in various formats
3. **Improve**: Create v2.0 prompt with explicit date format handling
4. **Test**: Run evaluation on validation set
5. **Compare**: v2.0 achieves 0.92 recall on dates (vs 0.70 baseline)
6. **Deploy**: Activate v2.0 as the production prompt
7. **Monitor**: Track date extraction accuracy over next week

### Results
- Date extraction recall improved from 0.70 → 0.92
- Overall F1 score improved from 0.78 → 0.87
- Extraction time decreased from 1500ms → 1200ms

## Future Enhancements

- [ ] Active learning: suggest which documents to label next
- [ ] Confidence calibration: adjust confidence thresholds
- [ ] Multi-model comparison: test different LLM models
- [ ] Automated prompt optimization: use LLM to suggest prompt improvements
- [ ] Batch evaluation: run evaluation on entire document sets
- [ ] Export evaluation reports to PDF/Excel
- [ ] Integration with CI/CD for prompt testing
