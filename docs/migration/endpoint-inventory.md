# Endpoint Inventory

Total endpoints discovered: **102**

| Group | Count |
|---|---:|
| `annotations` | 17 |
| `deployments` | 7 |
| `documents` | 5 |
| `evaluation` | 24 |
| `graph` | 5 |
| `health` | 1 |
| `ingest` | 2 |
| `providers` | 8 |
| `search` | 2 |
| `suggestions` | 5 |
| `taxonomy` | 20 |
| `timeline` | 2 |
| `tutorial` | 4 |

## Per Group

### `annotations`
- `GET` `/labels`
- `POST` `/labels`
- `GET` `/labels/{label_id}`
- `PUT` `/labels/{label_id}`
- `DELETE` `/labels/{label_id}`
- `POST` `/labels/suggest`
- `POST` `/labels/suggestions/{suggestion_id}/accept`
- `POST` `/labels/suggestions/{suggestion_id}/reject`
- `POST` `/documents/{document_id}/suggest-annotations`
- `GET` `/documents/{document_id}/annotations`
- `POST` `/documents/{document_id}/annotations`
- `GET` `/annotations/{annotation_id}`
- `DELETE` `/annotations/{annotation_id}`
- `DELETE` `/documents/{document_id}/annotations`
- `GET` `/documents/{document_id}/annotations/stats`
- `GET` `/annotations/export`
- `GET` `/documents/{document_id}/export`

### `deployments`
- `POST` `/versions`
- `GET` `/projects/{project_id}/versions`
- `GET` `/projects/{project_id}/active`
- `POST` `/projects/{project_id}/versions/{version_id}/activate`
- `POST` `/projects/{project_id}/extract`
- `POST` `/projects/{project_id}/versions/{version_id}/extract`
- `POST` `/projects/{project_id}/v/{version}/extract`

### `documents`
- `GET` `/documents`
- `GET` `/documents/{document_id}`
- `GET` `/documents/{document_id}/file`
- `DELETE` `/documents/{document_id}`
- `POST` `/documents/{document_id}/reprocess`

### `evaluation`
- `POST` `/benchmarks/datasets`
- `GET` `/benchmarks/datasets`
- `POST` `/benchmarks/datasets/{dataset_id}/documents`
- `POST` `/run-benchmark`
- `GET` `/benchmarks/runs/{run_id}`
- `POST` `/run`
- `POST` `/run-project`
- `GET` `/results/{evaluation_id}`
- `DELETE` `/results/{evaluation_id}`
- `GET` `/summary/aggregate`
- `GET` `/compare/prompts`
- `POST` `/prompts`
- `GET` `/prompts/{version_id}`
- `GET` `/prompts`
- `PATCH` `/prompts/{version_id}`
- `DELETE` `/prompts/{version_id}`
- `GET` `/prompts/active/current`
- `POST` `/field-prompts`
- `GET` `/field-prompts/version/{version_id}`
- `GET` `/field-prompts/list`
- `PATCH` `/field-prompts/version/{version_id}`
- `DELETE` `/field-prompts/version/{version_id}`
- `GET` `/field-prompts/active/current`
- `GET` `/field-prompts/active/by-document-type`

### `graph`
- `GET` `/graph`
- `GET` `/graph/entities`
- `GET` `/graph/entities/{entity_id}`
- `GET` `/graph/timeline`
- `GET` `/graph/stats`

### `health`
- `GET` `/health`

### `ingest`
- `POST` `/ingest`
- `GET` `/ingest/status`

### `providers`
- `GET` `/openai`
- `PUT` `/openai`
- `POST` `/openai/test`
- `GET` `/openai/models`
- `POST` `/openai/models`
- `PATCH` `/openai/models/{model_id}`
- `DELETE` `/openai/models/{model_id}`
- `POST` `/openai/models/{model_id}/test`

### `search`
- `GET` `/search`
- `POST` `/ask`

### `suggestions`
- `POST` `/documents/{document_id}/suggest`
- `POST` `/feedback`
- `GET` `/feedback`
- `GET` `/model/status`
- `POST` `/model/train`

### `taxonomy`
- `POST` `/taxonomy/field-assistant`
- `GET` `/taxonomy/fields`
- `POST` `/taxonomy/fields`
- `GET` `/taxonomy/fields/{field_id}`
- `PUT` `/taxonomy/fields/{field_id}`
- `DELETE` `/taxonomy/fields/{field_id}`
- `GET` `/taxonomy/types`
- `POST` `/taxonomy/types`
- `GET` `/taxonomy/types/{type_id}`
- `GET` `/taxonomy/types/{type_id}/schema-versions`
- `PUT` `/taxonomy/types/{type_id}`
- `DELETE` `/taxonomy/types/{type_id}`
- `POST` `/documents/{document_id}/classify`
- `POST` `/documents/{document_id}/auto-classify`
- `GET` `/documents/{document_id}/classification`
- `DELETE` `/documents/{document_id}/classification`
- `GET` `/taxonomy/types/{type_id}/documents`
- `POST` `/documents/{document_id}/extract`
- `GET` `/documents/{document_id}/extraction`
- `DELETE` `/documents/{document_id}/extraction`

### `timeline`
- `GET` `/timeline`
- `GET` `/timeline/range`

### `tutorial`
- `POST` `/tutorial/setup`
- `GET` `/tutorial/status`
- `POST` `/tutorial/reset`
- `GET` `/tutorial/sample-documents`
