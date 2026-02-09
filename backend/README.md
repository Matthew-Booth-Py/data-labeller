# Unstructured Unlocked - Backend

The backend API for Unstructured Unlocked, a document intelligence system for temporal analysis.

## Quick Start

### Prerequisites

- Python 3.12+
- [UV](https://docs.astral.sh/uv/) (fast Python package manager)

### Installation

```bash
cd backend

# Install UV if you haven't already
# Windows:
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS/Linux:
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

### Running Locally

```bash
# Run the development server
uv run uvicorn uu_backend.api.main:app --reload --port 8000

# Or use the module directly
uv run python -m uu_backend.api.main
```

### Running with Docker

```bash
# From the project root
docker-compose up --build
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check and service status |
| `/api/v1/ingest` | POST | Upload and process documents |
| `/api/v1/ingest/status` | GET | Get ingestion statistics |
| `/api/v1/timeline` | GET | Get documents grouped by date |
| `/api/v1/timeline/range` | GET | Get date range of all documents |
| `/api/v1/documents` | GET | List all documents |
| `/api/v1/documents/{id}` | GET | Get a specific document |
| `/api/v1/documents/{id}` | DELETE | Delete a document |

## API Documentation

Once running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
backend/
├── src/uu_backend/
│   ├── api/
│   │   ├── main.py           # FastAPI application
│   │   └── routes/           # API endpoints
│   ├── database/
│   │   └── vector_store.py   # ChromaDB operations
│   ├── ingestion/
│   │   ├── converter.py      # MarkItDown wrapper
│   │   ├── chunker.py        # Document chunking
│   │   └── dates.py          # Date extraction
│   ├── models/               # Pydantic models
│   └── config.py             # Settings
├── pyproject.toml            # Project configuration
└── Dockerfile
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | API bind host |
| `API_PORT` | `8000` | API port |
| `DEBUG` | `false` | Enable debug mode |
| `CHROMA_PERSIST_DIRECTORY` | `./data/chroma` | ChromaDB storage path |
| `CHUNK_SIZE` | `1000` | Characters per chunk |
| `CHUNK_OVERLAP` | `200` | Overlap between chunks |
| `CORS_ORIGINS` | `["http://localhost:3000"]` | Allowed CORS origins |

## Development

```bash
# Install dev dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Format code
uv run ruff format .

# Lint code
uv run ruff check .
```
