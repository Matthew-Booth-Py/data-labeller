# Phase Checklist

## Phase 0
- [x] Endpoint inventory generated (`backend/tests/migration/endpoint_inventory.json`)
- [x] Route group map documented
- [x] Smoke script added (`backend/scripts/smoke_frontend_flows.sh`)
- [x] Contract fixture + baseline health shape test added

## Phase 1
- [x] Minimal Django + DRF dependencies added
- [x] Django project scaffolded (`uu_backend.django_project`)
- [x] Composite ASGI dispatcher added (`uu_backend.asgi_dispatcher`)
- [x] Runtime flags added (`DATA_BACKEND`, `ASYNC_EXECUTOR`)
- [x] Backend docker entrypoint switched to dispatcher

## Phase 2
- [x] Wave A DRF endpoints implemented (`health`, `timeline`, `search`)
- [x] Celery app wiring added
- [x] Ingest async executor supports `inline`/`celery`
- [x] Docker Compose includes Redis + celery worker
- [x] Wave B migrated (`documents`, `graph`, `providers`)
- [x] Wave C migrated (`ingest`, `suggestions`, `tutorial`)
- [x] Wave D migrated (`taxonomy`, `annotations`, `deployments`, `evaluation`)

## Phase 3
- [x] Repository abstraction scaffold added
- [x] Django API routes switched from direct SQLite client calls to repository factory (`get_repository`)
- [x] Service-layer migration from direct SQLite calls to repository interface

## Phase 4
- [x] Initial Django ORM model scaffold (`DocumentTypeModel`)
- [x] SQLite import management command scaffold
- [x] Expanded ORM parity models for core SQLite domain tables (`django_data.models`)
- [x] SQLite -> ORM import command supports full table set (`import_sqlite`)
- [x] SQLite vs ORM row-count parity command added (`validate_sql_parity`)
- [x] Postgres-backed runtime cutover wiring (`DJANGO_DATABASE_URL` + compose service)
- [x] Runtime migration/import/parity commands documented and runnable

## Phase 5
- [x] Full Django ownership for all route groups in dispatcher
- [x] Wave D Django API no longer proxies through `django_api/fastapi_proxy.py`
- [x] Django API has no imports of legacy `uu_backend.api.routes.*` modules
- [x] FastAPI rollback controls removed from runtime configuration
