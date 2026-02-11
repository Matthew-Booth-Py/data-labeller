# Unstructured Unlocked

Unstructured Unlocked is a document extraction workbench focused on two outcomes:

1. Agentic schema-driven extraction: users define document types and field schemas, then run extraction that returns key-value outputs aligned to those fields.
2. Human-in-the-loop evaluation: teams label ground truth (with AI assistance), run evaluations, and track extraction quality over time.

## Core Product Goals

### 1) Agentic schema-driven extraction
- Define document types and field schemas per use case.
- Attach extraction prompts at the field level.
- Keep labels schema-derived (labels are not managed independently).
- Run extraction with prompt/model/field-version controls.
- Deploy extraction configurations as versioned API endpoints.

### 2) Evaluation with AI-assisted labeling
- Create annotations manually with AI suggestions to speed up throughput.
- Run evaluation across all labeled project documents.
- Track per-field and combined metrics (accuracy, recall, F1, completeness).
- Compare field prompt versions and measure impact by version.
- Use run history to decide when to promote a deployment version.

## Current Workflow

1. Upload documents.
2. Create/select a document type schema.
3. Add fields (manually or via AI field assistant).
4. Classify document types (manual + LLM).
5. Annotate documents with schema-derived labels.
6. Run extraction and inspect raw output.
7. Run evaluation across labeled docs.
8. Save a new deployment version and promote active version.

## What “Save as New Version” Does

Saving a new version creates a deployable extraction snapshot for the selected project/document type:
- Captures schema + field prompts + active versions at save time.
- Stores it as a semantic version (`0.0`, `0.1`, `0.2`, ...).
- Allows activation/deactivation via Deployment UI.
- Exposes extraction endpoints that return outputs using that frozen config.

## API (Deployment)

All routes are served by FastAPI under `/api/v1`.

- `POST /api/v1/deployments/versions`
  - Create a new deployment snapshot version.
- `GET /api/v1/deployments/projects/{project_id}/versions`
  - List versions for a project.
- `GET /api/v1/deployments/projects/{project_id}/active`
  - Get active version.
- `POST /api/v1/deployments/projects/{project_id}/versions/{version_id}/activate`
  - Promote a version to active.
- `POST /api/v1/deployments/projects/{project_id}/extract`
  - Extract with active version.
- `POST /api/v1/deployments/projects/{project_id}/v/{version}/extract`
  - Extract with a pinned version.

## Run Locally (Docker)

The app is expected to run with Docker Compose.

```bash
docker compose build
docker compose up -d
```

Frontend: `http://localhost:3000`  
Backend API: `http://localhost:8000`

## Environment

Use your `.env` file. Important keys include:
- `OPENAI_API_KEY`
- model defaults/settings used by extraction/evaluation
- storage paths and runtime config

## Repo Layout

- `backend/` FastAPI, extraction, evaluation, persistence
- `frontend/` React app (schema, labeling, eval, deployment UI)
- `docs/` implementation notes and guides
- `data/` local runtime storage

## Notes

- Tutorial sample PDFs in `backend/sample_docs/` are required by tutorial setup and should remain.
- Labels are generated from schema fields by design.
- Evaluations are intended to be run over all labeled docs in the selected project/document type.
