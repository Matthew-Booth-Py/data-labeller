# Repository Context

## Project Purpose
This repository is a schema-driven document intelligence workbench. Its main use case is turning recurring business documents into schema-aligned structured output through a workflow that supports document ingestion, schema definition, document classification, ground-truth supervision, extraction quality evaluation, and versioned deployment endpoints.

## Primary Workflows
- Ingest source documents and convert them into searchable text or layout-preserving content.
- Define document type schemas, including nested fields and table-oriented array structures.
- Classify each document into the appropriate document type before extraction.
- Build and refresh retrieval indexes so extraction can use document context effectively.
- Create, review, and approve ground-truth annotations manually or from AI suggestions.
- Run retrieval-backed extraction against the active schema and prompts.
- Evaluate extraction output against approved labels to measure quality and guide iteration.
- Save stable configuration snapshots and expose them through versioned extraction endpoints.

## Core Components
- Frontend workspace/studio for project-oriented schema design, document review, labelling, evaluation, and deployment operations.
- Backend API for ingestion, taxonomy management, extraction, annotation workflows, evaluation, retrieval, and deployment version management.
- Async processing for retrieval indexing and evaluation jobs using a task queue and worker processes.
- Persistent storage for documents, schemas, classifications, labels, extractions, evaluations, prompt versions, and deployment snapshots.
- Contextual retrieval stack that combines chunking, summarization/context generation, embeddings, vector search, keyword search, and optional reranking.

## Important Implementation Realities
- "Projects" are primarily a frontend workspace concept stored in browser state rather than a first-class backend projects table.
- Retrieval indexing is part of the intended extraction path; extraction may be unavailable or fail until indexing has completed.
- Labelling exists to support ground truth, evaluation, and iteration; it is an important workflow but not the sole purpose of the product.
- Deployment extraction can run from saved configuration snapshots without requiring the full interactive studio workflow.

## Workflow At A Glance
ingest -> schema design -> classification -> retrieval indexing -> label review -> extraction -> evaluation -> deployment
