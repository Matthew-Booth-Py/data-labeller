# Unstructured Unlocked

Schema-driven document extraction workbench for ingesting business documents, defining extraction schemas, supervising labels, measuring extraction quality, and publishing versioned extraction endpoints.

This repository is not a generic data labelling library. The codebase implements a full document intelligence product with these stages:

1. Ingest documents and convert them into searchable text.
2. Define document types and schema fields.
3. Classify documents into a document type.
4. Index documents for contextual retrieval.
5. Generate and approve ground-truth annotations.
6. Run structured extraction against the active schema.
7. Evaluate extraction output against approved labels.
8. Snapshot the current configuration into a deployment version and expose a stable extraction endpoint.

## What The Product Does

The application is built for semi-structured document workflows such as:

- insurance claims
- invoices and receipts
- forms and certificates
- table-heavy financial filings
- any repeatable document family that needs schema-aligned JSON output

The strongest product signals in the code are:

- document-type schemas with nested fields and table-aware arrays
- AI field suggestion and screenshot-assisted schema design
- manual and automatic document classification
- retrieval-first extraction, including table-aware PDF handling
- AI-generated annotation suggestions mapped back onto source documents
- ground-truth storage for evaluation
- versioned deployment endpoints per project/workspace

## Core Workflow

### 1. Create a workspace

The frontend groups work into "projects". Project records are persisted in the backend (`/api/v1/projects`) and associated with their documents, schemas, labels, and deployment versions.

### 2. Ingest documents

Documents are uploaded through `POST /api/v1/ingest`. The backend stores the original file, converts it into text/markdown, saves metadata, and queues contextual retrieval indexing.

### 3. Define document types and fields

Schemas are defined as document types with field prompts, nested object fields, and array-of-object fields for tables. The field assistant can suggest field definitions from natural language and screenshots.

### 4. Classify documents

Each document must be associated with a document type before structured extraction is meaningful. Classification can be manual or LLM-assisted.

### 5. Wait for contextual retrieval indexing

Contextual retrieval is not optional in the main extraction path. If a document has not finished indexing, extraction is expected to fail until indexing completes.

### 6. Label and approve ground truth

The labeller supports:

- text span annotations
- bounding-box annotations
- table-row annotations

The system can also generate AI annotation suggestions and save approved suggestions as ground truth.

### 7. Run extraction

Extraction is schema-driven and optimized for exact-value capture. For PDFs with table-like fields, the backend uses retrieval-vision selection and table-aware PDF extraction so output stays aligned with the source document.

### 8. Evaluate and deploy

Evaluation compares extracted output against approved labels and computes quality metrics. Once the schema and prompts are in a good state, the current configuration can be saved as a deployment version and exposed through a versioned extraction endpoint.

## Architecture

### Backend

- Django + Django REST Framework API
- ASGI entrypoint via `uvicorn`
- Celery worker for retrieval indexing and async evaluation tasks
- PostgreSQL for persistent app data
- Redis for Celery broker/result backend
- Qdrant, Chroma, and BM25-based contextual retrieval stack
- OpenAI or Azure OpenAI for classification, field suggestion, extraction, and evaluation

### Frontend

- React 19
- TanStack Query
- Wouter routing
- Radix UI components
- Express host for the frontend shell
- Vite in development, bundled server in production

## Supported Input Types

The ingestion converter currently accepts:

- `.pdf`
- `.docx`
- `.doc`
- `.xlsx`
- `.xls`
- `.pptx`
- `.ppt`
- `.html`
- `.htm`
- `.txt`
- `.md`
- `.csv`
- `.json`
- `.xml`
- `.jpg`
- `.jpeg`
- `.png`
- `.gif`
- `.webp`
- `.eml`
- `.msg`

PDFs receive special handling. Bordered tables are converted into markdown tables, while non-bordered financial tables use layout-preserving extraction so column alignment is not lost.

## Running With Docker Compose

Docker Compose is the most reliable way to run the full stack because it brings up PostgreSQL, Redis, Qdrant, the backend, the frontend, and the Celery worker together.

### Prerequisites

- Docker
- Docker Compose
- an OpenAI API key, or Azure OpenAI credentials

### Required environment

At minimum:

```bash
export OPENAI_API_KEY=your_key_here
```

If you are using Azure OpenAI instead:

```bash
export USE_AZURE_OPENAI=true
export AZURE_OPENAI_ENDPOINT=...
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_API_VERSION=2024-12-01-preview
```

### Optional environment

These variables are not required but enable additional capabilities:

```bash
# Override the model used for extraction and classification (defaults to a GPT-4o variant)
export OPENAI_MODEL=gpt-4o

# Override the model used for context generation during retrieval indexing
export CONTEXT_MODEL=gpt-4o-mini

# Azure Document Intelligence for OCR-quality PDF extraction
export AZURE_DI_ENDPOINT=...
export AZURE_DI_KEY=...

# Cohere reranking to improve retrieval quality
export CO_API_KEY=...
export CO_RERANK_ENDPOINT=...
```

### Start the stack

```bash
docker compose up --build
```

### Default URLs

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8000](http://localhost:8000)
- Health: [http://localhost:8000/health](http://localhost:8000/health)
- Swagger docs: [http://localhost:8000/api/docs/](http://localhost:8000/api/docs/)
- ReDoc: [http://localhost:8000/redoc](http://localhost:8000/redoc)

The backend container runs Django migrations before starting the API server.

## Local Development

### Backend

```bash
cd backend
uv sync

export OPENAI_API_KEY=your_key_here
export DJANGO_DATABASE_URL=postgres://uu:uu@localhost:5432/uu_django
export REDIS_URL=redis://localhost:6379/0
export DJANGO_SETTINGS_MODULE=uu_backend.django_project.settings.local

uv run python manage.py migrate
uv run uvicorn uu_backend.asgi_dispatcher:application --reload --host 0.0.0.0 --port 8000
```

### Celery worker

```bash
cd backend
export OPENAI_API_KEY=your_key_here
export DJANGO_DATABASE_URL=postgres://uu:uu@localhost:5432/uu_django
export REDIS_URL=redis://localhost:6379/0
export DJANGO_SETTINGS_MODULE=uu_backend.django_project.settings.local

uv run celery -A uu_backend.django_project.celery_app worker -l info
```

### Frontend

```bash
cd frontend
npm ci
PORT=3000 VITE_API_URL=http://localhost:8000 npm run dev
```

If you run the frontend on an origin other than `http://localhost:3000`, update backend CORS settings in `backend/settings.yml` or via `CORS_ORIGINS`.

## Important Behaviour Notes

- Extraction is driven by document type schema. Uploading a document alone is not enough.
- Contextual retrieval indexing is queued during ingest and must complete before the main extraction path is usable.
- Table extraction is a first-class use case. Arrays of objects are used to represent table rows.
- Extraction aims to preserve raw source values exactly rather than normalizing them.
- Evaluation is grounded in stored ground-truth annotations, not just ad hoc comparison.
- Deployment versions are immutable snapshots of schema, prompts, and model settings for a given workspace.
- The frontend "project" concept maps to a backend-persisted project record. The backend stores documents, schemas, labels, evaluations, and deployment versions, all associated with a project.

## Key Endpoints

### Platform

- `GET /health`
- `GET /api/docs/`
- `GET /redoc`

### Ingestion and documents

- `POST /api/v1/ingest`
- `GET /api/v1/ingest/status`
- `GET /api/v1/documents`
- `GET /api/v1/documents/{document_id}`
- `GET /api/v1/documents/{document_id}/file`
- `POST /api/v1/documents/{document_id}/reindex-retrieval`

### Taxonomy and extraction

- `GET /api/v1/taxonomy/types`
- `POST /api/v1/taxonomy/types`
- `POST /api/v1/taxonomy/field-assistant`
- `POST /api/v1/taxonomy/analyze-image`
- `POST /api/v1/documents/{document_id}/classify`
- `POST /api/v1/documents/{document_id}/auto-classify`
- `POST /api/v1/documents/{document_id}/extract`
- `GET /api/v1/documents/{document_id}/extraction`

### Ground truth and evaluation

- `GET /api/v1/documents/{document_id}/ground-truth`
- `POST /api/v1/documents/{document_id}/ground-truth`
- `POST /api/v1/documents/{document_id}/suggest-annotations`
- `POST /api/v1/annotations/{annotation_id}/approve`
- `POST /api/v1/evaluation/run`
- `GET /api/v1/evaluation/results`
- `GET /api/v1/evaluation/summary`

### Retrieval and deployment

- `GET /api/v1/search?q=...`
- `POST /api/v1/deployments/versions`
- `GET /api/v1/deployments/projects/{project_id}/versions`
- `POST /api/v1/deployments/projects/{project_id}/versions/{version_id}/activate`
- `POST /api/v1/deployments/projects/{project_id}/extract`
- `POST /api/v1/deployments/projects/{project_id}/v/{version}/extract`

## Example Deployment Flow

1. Create a workspace in the UI.
2. Upload and classify a set of documents.
3. Finalize the document type schema and prompts.
4. Approve labels and verify evaluation quality.
5. Click `Save as New Version` in the workspace.
6. Call the active extraction endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/deployments/projects/<project_id>/extract \
  -F "file=@invoice.pdf"
```

## Repository Layout

```text
backend/   Django API, models, services, Celery tasks, tests
frontend/  React application, frontend shell server, styling
docs/      supporting notes, guides, and implementation docs
data/      local runtime data: document files, retrieval artifacts, Qdrant PDF storage
```

## Testing

### Backend

```bash
cd backend
uv run pytest tests/
```

### Frontend type check

```bash
cd frontend
npm run check
```

## Current Positioning

The clearest way to think about this repository is:

`schema-driven document extraction studio with labelling, evaluation, and deployment`

That matches the code more closely than "data labeller" on its own.
