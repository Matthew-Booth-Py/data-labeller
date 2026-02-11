# Django Migration Dashboard

## Current Phase Status

| Phase | Status | Notes |
|---|---|---|
| Phase 0: Baseline + Harness | Complete | Endpoint inventory, smoke script, and contract harness in repo |
| Phase 1: Django Foundation + Dispatcher | Complete | Django scaffold and composite dispatcher in place |
| Phase 2: DRF Migration + Celery | Complete | Wave A-D implemented under `django_api` with Celery task execution |
| Phase 3: Repository Abstraction | Complete | Django API and service layers use repository abstraction backed by Django ORM |
| Phase 4: ORM + Postgres Migration | Complete | Postgres runtime wiring and Django ORM persistence are in place |
| Phase 5: Decommission | Complete | Dispatcher is Django-only; Django API no longer imports legacy route modules |

## Route Group Ownership

| Group | Owner | Default Runtime |
|---|---|---|
| health | Django (Wave A) | Django |
| timeline | Django (Wave A) | Django |
| search | Django (Wave A) | Django |
| documents | Django (Wave B) | Django |
| graph | Django (Wave B) | Django |
| providers | Django (Wave B) | Django |
| ingest | Django (Wave C) | Django |
| suggestions | Django (Wave C) | Django |
| tutorial | Django (Wave C) | Django |
| taxonomy | Django (Wave D) | Django |
| annotations | Django (Wave D) | Django |
| deployments | Django (Wave D) | Django |
| evaluation | Django (Wave D) | Django |

## Operational Notes

- All API groups are served by Django.
- Celery worker can be started via Docker Compose service `celeryworker`.
- Redis is included for queue transport.
