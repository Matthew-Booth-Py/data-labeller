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
- [x] Backend docker entrypoint switched to dispatcher

## Phase 2
- [x] Wave A DRF endpoints implemented (`health`, `timeline`, `search`)
- [x] Celery app wiring added
- [x] Ingest pipeline runs through Celery task queue
- [x] Docker Compose includes Redis + celery worker
- [x] Wave B migrated (`documents`, `graph`, `providers`)
- [x] Wave C migrated (`ingest`, `suggestions`, `tutorial`)
- [x] Wave D migrated (`taxonomy`, `annotations`, `deployments`, `evaluation`)

## Phase 3
- [x] Repository abstraction scaffold added
- [x] Django API routes switched to repository factory (`get_repository`)
- [x] Service-layer data access standardized on repository interface

## Phase 4
- [x] Initial Django ORM model scaffold (`DocumentTypeModel`)
- [x] Expanded ORM models for core domain tables (`django_data.models`)
- [x] Postgres-backed runtime cutover wiring (`DJANGO_DATABASE_URL` + compose service)
- [x] Runtime migrations documented and runnable

## Phase 5
- [x] Full Django ownership for all route groups in dispatcher
- [x] Django API has no imports of legacy `uu_backend.api.routes.*` modules
- [x] Legacy rollback controls removed from runtime configuration
