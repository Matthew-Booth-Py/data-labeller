# Roadmap: Agentic Extraction + Human-in-the-Loop Evaluation

## Scope

This roadmap operationalizes the two core goals:

1. Agentic schema-driven extraction for document types and reusable fields
2. Evaluation against human-labeled ground truth, accelerated by AI suggestions

It is organized as a practical build plan with clear code touchpoints and acceptance criteria.

## Current Baseline (Already in Repo)

- Schema-aware document types and extraction endpoints
- AI-assisted schema-based annotation suggestions (`suggest-annotations`)
- Prompt versions and benchmark dataset/run endpoints
- Evaluation metrics (accuracy, precision, recall, F1)

Key existing modules:

- Backend API: `backend/src/uu_backend/django_api/taxonomy.py`
- Backend API: `backend/src/uu_backend/django_api/annotations.py`
- Backend API: `backend/src/uu_backend/django_api/evaluation.py`
- Backend services: `backend/src/uu_backend/services/extraction_service.py`
- Backend services: `backend/src/uu_backend/services/schema_based_suggestion_service.py`
- Backend services: `backend/src/uu_backend/services/evaluation_service.py`
- Persistence: `backend/src/uu_backend/repositories/django_repo.py`
- Frontend UI: `frontend/client/src/pages/FieldsLibrary.tsx`
- Frontend UI: `frontend/client/src/components/workspace/EvaluateView.tsx`
- Frontend API client: `frontend/client/src/lib/api.ts`

## Milestones

## Phase 1 (Weeks 1-2): Foundation for Reliable Iteration

### 1. Version and trace all extraction configs

Outcome: Every extraction/evaluation run is reproducible.

Build:

- Add immutable version records for:
  - document type schema
  - extraction prompt/system prompt
  - normalization rules/post-processing
- Persist config version IDs with extraction results and evaluations.

Touchpoints:

- `backend/src/uu_backend/models/taxonomy.py`
- `backend/src/uu_backend/models/evaluation.py`
- `backend/src/uu_backend/repositories/django_repo.py`
- `backend/scripts/smoke_frontend_flows.sh`
- `backend/src/uu_backend/django_api/taxonomy.py`
- `backend/src/uu_backend/django_api/evaluation.py`

Acceptance:

- Any evaluation record can answer: "Which exact schema/prompt/normalizer produced this result?"

### 2. Golden set schema test harness

Outcome: Safe changes before rollout.

Build:

- Add benchmark/golden set runner by document type and split.
- Add regression comparison endpoint: current vs baseline run.
- Add failure summary grouped by field.

Touchpoints:

- `backend/src/uu_backend/services/evaluation_service.py`
- `backend/src/uu_backend/models/evaluation.py`
- `backend/src/uu_backend/django_api/evaluation.py`
- `backend/tests/test_evaluation.py`

Acceptance:

- Can run one command/API call and get pass/fail against quality gates by field and aggregate F1.

### 3. Evaluation metric expansion (field semantics)

Outcome: Metrics reflect real extraction quality, not just strict string equality.

Build:

- Add per-field comparator modes:
  - exact
  - normalized (whitespace/casing/punctuation/date/number canonicalization)
  - fuzzy threshold
- Add explicit "unsupported/empty/abstained" outcome categories.

Touchpoints:

- `backend/src/uu_backend/services/evaluation_service.py`
- `backend/src/uu_backend/models/evaluation.py`
- `backend/tests/test_evaluation.py`

Acceptance:

- Evaluation responses expose comparator mode and per-field reason codes.

## Phase 2 (Weeks 3-6): Agentic Workflow + Labeling Throughput

### 4. Real global field library (replace local mock state)

Outcome: Reusable field templates become a first-class persisted asset.

Build:

- Add backend CRUD for global fields and field groups.
- Allow schema fields to reference global templates (copy-on-write or linked mode).
- Replace `FieldsLibrary` mock data with API-backed state.

Touchpoints:

- `frontend/client/src/pages/FieldsLibrary.tsx`
- `frontend/client/src/lib/api.ts`
- `frontend/server/routes.ts` (if proxy routing needed)
- `backend/src/uu_backend/django_api/taxonomy.py` (or new `fields.py`)
- `backend/src/uu_backend/models/taxonomy.py`
- `backend/src/uu_backend/repositories/django_repo.py`

Acceptance:

- Field templates persist across sessions and can be reused across multiple document types.

### 5. Agentic setup and tuning workflows

Outcome: Users can run guided flows instead of ad hoc manual sequences.

Build:

- Add workflow endpoints and UI flows:
  - New Document Type Setup
  - Batch Suggest + Review
  - Evaluation and Retune
- Store workflow runs and checkpoints.

Touchpoints:

- `backend/src/uu_backend/services/suggestion_service.py`
- `backend/src/uu_backend/services/schema_based_suggestion_service.py`
- `frontend/client/src/pages/ProjectWorkspace.tsx`

Acceptance:

- A new user can complete schema creation, annotation generation, and first benchmark run from one guided flow.

### 6. Confidence calibration + triage lanes

Outcome: Faster labeling with controlled risk.

Build:

- Calibrate confidence by field from historical evaluation outcomes.
- Introduce three lanes:
  - auto-accept
  - review-required
  - abstain
- Add threshold settings per document type/field.

Touchpoints:

- `backend/src/uu_backend/services/schema_based_suggestion_service.py`
- `backend/src/uu_backend/services/evaluation_service.py`
- `backend/src/uu_backend/models/suggestion.py`
- `backend/src/uu_backend/repositories/django_repo.py`
- `frontend/client/src/components/workspace/LabelStudio.tsx`

Acceptance:

- Measurable reduction in manual review time with no statistically significant drop in field-level precision.

## Phase 3 (Weeks 7-10): Quality Governance and Production Readiness

### 7. Error taxonomy and root-cause analytics

Outcome: Faster debugging and better prioritization.

Build:

- Capture failure reason categories:
  - OCR issue
  - schema ambiguity
  - prompt miss
  - normalization mismatch
  - extraction hallucination
- Add dashboards for top failing fields/reasons.

Touchpoints:

- `backend/src/uu_backend/services/evaluation_service.py`
- `backend/src/uu_backend/models/evaluation.py`
- `frontend/client/src/components/workspace/EvaluateView.tsx`
- `frontend/client/src/components/workspace/EvaluationBoard.tsx`

Acceptance:

- Top failure modes are visible without reading raw logs.

### 8. Slice-based quality and drift monitoring

Outcome: Detect hidden regressions early.

Build:

- Evaluate and compare by slices:
  - subtype/vendor/template/layout quality
  - ingestion source
  - date range
- Add scheduled benchmark runs and drift alerts.

Touchpoints:

- `backend/src/uu_backend/models/evaluation.py`
- `backend/src/uu_backend/repositories/django_repo.py`
- `backend/src/uu_backend/django_api/evaluation.py`
- `frontend/client/src/pages/Dashboard.tsx`
- `frontend/client/src/components/workspace/DriftMap.tsx`

Acceptance:

- Regression alerts trigger when slice-level gates are breached even if aggregate metrics remain stable.

### 9. CI release gates for extraction quality

Outcome: Prevent quality regressions reaching production.

Build:

- Add benchmark runner CLI/script for CI.
- Fail CI if:
  - aggregate F1 drops past threshold
  - required fields fail minimum precision/recall

Touchpoints:

- `backend/tests/test_evaluation.py`
- `backend/scripts/` (new CI evaluation runner)
- `.github/workflows/` (new workflow)

Acceptance:

- Pull requests with extraction regressions are blocked automatically.

## Execution Checklist

## Sprint A (next 2 weeks)

- Implement config version linkage in extraction + evaluation records
- Ship golden set benchmark gates and baseline comparison
- Add comparator modes and reason codes in evaluation output
- Replace `FieldsLibrary` mock-only behavior with persisted backend data

Definition of done:

- Reproducible eval runs with version metadata
- One benchmark dataset can gate prompt/schema changes
- Fields library is persistent and shared

## Sprint B (following 4 weeks)

- Guided agentic workflows in onboarding/workspace
- Confidence calibration and triage lanes
- Field-level error taxonomy in evaluation UI

Definition of done:

- Labeling throughput increases with stable precision
- Users can complete setup-to-evaluation without manual endpoint sequencing

## Success Metrics

- Time-to-first-accurate-schema (TTFAS): from upload to first benchmark pass
- Labeling throughput: documents/hour and fields/hour
- Human correction rate after auto-suggestion
- Field-level precision/recall for critical fields
- Regression frequency caught pre-release by CI gates

## Risks and Mitigations

- Risk: Strict schema coupling reduces flexibility for edge cases
  - Mitigation: per-field comparator modes + abstain lane
- Risk: Faster auto-accept reduces ground truth quality
  - Mitigation: stratified spot-audit + confidence calibration
- Risk: Added workflow complexity
  - Mitigation: default templates with optional advanced controls
