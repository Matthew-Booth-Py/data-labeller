# Contextual Retrieval Fix - Per-Document Collections

## Problem
The contextual retrieval system was failing with ChromaDB errors like:
```
ChromaDB search error (possibly corrupted index): Error executing plan: Internal error: Error finding id
```

The root cause was that **all documents were sharing a single ChromaDB collection**, which caused:
- Data corruption and loss between indexing operations
- Search failures when trying to retrieve chunks
- 0 chunks retrieved during extraction (even though indexing appeared successful)

## Solution
Refactored `ChromaVectorStore` to use **one ChromaDB collection per document** instead of a shared collection.

### Changes Made

#### File: `backend/src/uu_backend/services/contextual_retrieval/vector_store.py`

**Key Changes:**
1. **Per-Document Collections**: Each document now gets its own isolated ChromaDB collection named `doc_{document_id}`
2. **Collection Management**: Added `_get_collection_name()` and `_get_or_create_collection()` methods
3. **Updated Operations**:
   - `add()`: Groups chunks by document and stores in separate collections
   - `search()`: Requires `filter_doc_id` and searches within that document's collection
   - `delete_document()`: Deletes the entire collection for that document
   - `get_document_chunks()`: Retrieves from document-specific collection
   - `count()`: Sums across all document collections
   - `clear()`: Deletes all document collections

### Benefits
- **Isolation**: Each document's index is completely isolated
- **Reliability**: No cross-document corruption or data loss
- **Performance**: Smaller collections = faster queries
- **Debugging**: Easy to identify and fix issues per document

### Testing
After the fix:
1. Restarted backend and celeryworker containers
2. Triggered reindexing: `POST /api/v1/documents/{document_id}/reindex-retrieval`
3. Indexing completed successfully with 6 chunks
4. Collections are now stored separately in ChromaDB

### Usage
The extraction API automatically uses per-document collections:
```
POST /api/v1/documents/{document_id}/extract?use_retrieval=true
```

The system will:
1. Search within the document's dedicated collection
2. Retrieve relevant chunks for each schema field
3. Use retrieved context for extraction

### Migration Notes
- Existing shared collections will remain but won't be used
- Documents need to be reindexed to create per-document collections
- Use the reindex endpoint for each document or trigger a full reindex

### Next Steps
To reindex all documents:
```bash
# Via API (recommended - queues Celery tasks)
POST /api/v1/documents/{document_id}/reindex-retrieval

# Or trigger full reindex (if endpoint exists)
POST /api/v1/retrieval/reindex-all
```
