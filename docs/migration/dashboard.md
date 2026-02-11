# Django Migration Dashboard

## Current Phase Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0: Baseline + Harness | In Progress | Endpoint inventory, smoke script, and contract harness added |
| Phase 1: Django Foundation + Dispatcher | In Progress | Django project scaffolded; dispatcher active with feature flags |
| Phase 2: DRF Migration + Celery | In Progress | Wave A-D routed through Django (`health`, `timeline`, `search`, `documents`, `graph`, `providers`, `ingest`, `suggestions`, `tutorial`, `taxonomy`, `annotations`, `deployments`, `evaluation`) |
| Phase 3: Repository Abstraction | Not Started | Pending adapter layer implementation |
| Phase 4: ORM + Postgres Migration | Not Started | Pending Django model parity and import tooling |
| Phase 5: FastAPI Decommission | Not Started | Pending full route parity in Django |

## Route Group Ownership

| Group | Owner | Default Runtime |
|---|---|---|
| health | Django (Wave A) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `health` |
| timeline | Django (Wave A) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `timeline` |
| search | Django (Wave A) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `search` |
| documents | Django (Wave B) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `documents` |
| graph | Django (Wave B) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `graph` |
| providers | Django (Wave B) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `providers` |
| ingest | Django (Wave C) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `ingest` |
| suggestions | Django (Wave C) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `suggestions` |
| tutorial | Django (Wave C) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `tutorial` |
| taxonomy | Django (Wave D) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `taxonomy` |
| annotations | Django (Wave D) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `annotations` |
| deployments | Django (Wave D) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `deployments` |
| evaluation | Django (Wave D) | FastAPI until `DJANGO_MIGRATED_GROUPS` includes `evaluation` |

## Feature Flags

- `DJANGO_MIGRATED_GROUPS`: comma-separated migrated groups, e.g. `health,timeline,search,documents,graph,providers,ingest,suggestions,tutorial,taxonomy,annotations,deployments,evaluation`
- `DATA_BACKEND`: `sqlite` (default), `dual`, `django`
- `ASYNC_EXECUTOR`: `inline` (default), `celery`

## Operational Notes

- Default behavior is backwards-compatible: no migrated groups means all requests go through FastAPI.
- Celery worker can be started via Docker Compose service `celeryworker`.
- Redis is included for queue transport in migration phase 2.
