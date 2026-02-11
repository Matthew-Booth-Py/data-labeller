# Route Group Map

This map drives `DJANGO_MIGRATED_GROUPS` cutover behavior in `uu_backend.asgi_dispatcher`.

## Wave A
- `health`: `/health`, `/api/v1/health`
- `timeline`: `/api/v1/timeline`, `/api/v1/timeline/range`
- `search`: `/api/v1/search`, `/api/v1/ask`

## Wave B
- `documents`
- `graph`
- `providers`

## Wave C
- `ingest`
- `suggestions`
- `tutorial`

## Wave D
- `taxonomy`
- `annotations`
- `deployments`
- `evaluation`
