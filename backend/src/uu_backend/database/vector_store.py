"""Neo4j-based vector store for document storage and retrieval."""

from collections import defaultdict
from datetime import date, datetime

import tiktoken
from neo4j import GraphDatabase

from uu_backend.config import get_settings
from uu_backend.models.document import Document, DocumentChunk, DocumentMetadata, DocumentSummary
from uu_backend.models.timeline import (
    DateRange,
    TimelineDocument,
    TimelineEntry,
    TimelineResponse,
)


class VectorStore:
    """Neo4j-based vector store for documents."""

    def __init__(self):
        """Initialize the vector store."""
        settings = get_settings()
        
        # Initialize Neo4j driver
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        self._database = settings.neo4j_database
        self._token_encoding = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(self._token_encoding.encode(text))

    def add_document(self, document: Document) -> None:
        """
        Add a document and its chunks to the store.
        
        Note: Documents are now managed by GraphIngestionService.
        This method is kept for API compatibility but does minimal work.

        Args:
            document: The document to add
        """
        # Documents and chunks are stored in Neo4j by GraphIngestionService
        # This is a no-op for backward compatibility
        pass

    def update_document_content(self, document_id: str, new_content: str) -> bool:
        """
        Update document content after reprocessing.
        
        Note: Document reindexing is handled by GraphIngestionService.
        
        Args:
            document_id: Document ID
            new_content: New content from reprocessing
            
        Returns:
            True if successful
        """
        from uu_backend.services.graph_ingestion_service import get_graph_ingestion_service
        
        # Get existing document
        document = self.get_document(document_id)
        if not document:
            return False
        
        # Re-index through GraphIngestionService
        graph_service = get_graph_ingestion_service()
        graph_service.extract_and_store_entities(
            doc_id=document_id,
            content=new_content,
            document_date=document.date_extracted,
            filename=document.filename,
            file_type=document.file_type,
            created_at=document.created_at,
        )
        
        return True

    def get_document(self, document_id: str) -> Document | None:
        """
        Retrieve a document by ID from Neo4j.

        Args:
            document_id: The document ID

        Returns:
            The document or None if not found
        """
        with self._driver.session(database=self._database) as session:
            # Get document and its chunks
            result = session.run(
                """
                MATCH (d:Document {id: $doc_id})
                OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
                WITH d, c
                ORDER BY c.index
                RETURN d.id AS id,
                       d.filename AS filename,
                       d.file_type AS file_type,
                       d.date AS date_extracted,
                       d.created_at AS created_at,
                       collect({
                           id: c.id,
                           text: c.text,
                           index: c.index
                       }) AS chunks
                """,
                doc_id=document_id
            ).single()
            
            if not result:
                return None
            
            # Parse date
            date_extracted = None
            if result["date_extracted"]:
                try:
                    date_extracted = datetime.fromisoformat(result["date_extracted"])
                except (ValueError, TypeError):
                    pass
            
            created_at = datetime.now()
            if result["created_at"]:
                try:
                    created_at = datetime.fromisoformat(result["created_at"])
                except (ValueError, TypeError):
                    pass
            
            # Build chunks
            chunks = []
            full_content_parts = []
            for chunk_data in result["chunks"]:
                if chunk_data["id"]:  # Skip null chunks from OPTIONAL MATCH
                    chunk_text = chunk_data["text"] or ""
                    chunks.append(
                        DocumentChunk(
                            id=chunk_data["id"],
                            document_id=document_id,
                            content=chunk_text,
                            chunk_index=chunk_data["index"] or 0,
                            metadata={"document_id": document_id},
                        )
                    )
                    full_content_parts.append(chunk_text)
            
            full_content = "\n\n".join(full_content_parts) if full_content_parts else ""
            
            return Document(
                id=document_id,
                filename=result["filename"] or "Unknown",
                file_type=result["file_type"] or "",
                content=full_content,
                date_extracted=date_extracted,
                created_at=created_at,
                metadata=DocumentMetadata(
                    filename=result["filename"] or "Unknown",
                    file_type=result["file_type"] or "",
                    date_extracted=date_extracted,
                ),
                chunks=chunks,
            )

    def get_all_documents(self) -> list[DocumentSummary]:
        """
        Get all documents as summaries from Neo4j.

        Returns:
            List of document summaries
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                """
                MATCH (d:Document)
                OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
                WITH d, count(c) AS chunk_count, collect(c.text) AS chunks
                RETURN d.id AS id,
                       d.filename AS filename,
                       d.file_type AS file_type,
                       d.date AS date_extracted,
                       d.created_at AS created_at,
                       chunk_count,
                       chunks
                ORDER BY d.created_at DESC
                """
            )
            
            summaries = []
            for record in result:
                date_extracted = None
                if record["date_extracted"]:
                    try:
                        date_extracted = datetime.fromisoformat(record["date_extracted"])
                    except (ValueError, TypeError):
                        pass
                
                created_at = datetime.now()
                if record["created_at"]:
                    try:
                        created_at = datetime.fromisoformat(record["created_at"])
                    except (ValueError, TypeError):
                        pass
                
                # Calculate token count from chunks
                full_text = "\n\n".join(record["chunks"]) if record["chunks"] else ""
                token_count = self._count_tokens(full_text)
                
                summaries.append(
                    DocumentSummary(
                        id=record["id"],
                        filename=record["filename"] or "Unknown",
                        file_type=record["file_type"] or "",
                        date_extracted=date_extracted,
                        created_at=created_at,
                        chunk_count=int(record["chunk_count"] or 0),
                        token_count=token_count,
                    )
                )
            
            return summaries

    def get_timeline(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TimelineResponse:
        """
        Get documents grouped by date for timeline visualization from Neo4j.

        Args:
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            TimelineResponse with grouped documents
        """
        with self._driver.session(database=self._database) as session:
            # Build query with optional date filters
            cypher_query = """
            MATCH (d:Document)
            WHERE d.date IS NOT NULL
            """
            
            params = {}
            if start_date:
                cypher_query += " AND date(d.date) >= date($start_date)"
                params["start_date"] = start_date.isoformat()
            if end_date:
                cypher_query += " AND date(d.date) <= date($end_date)"
                params["end_date"] = end_date.isoformat()
            
            cypher_query += """
            OPTIONAL MATCH (c:Chunk)-[:FROM_DOCUMENT]->(d)
            WITH d, collect(c.text)[0..200] AS excerpt
            RETURN d.id AS id,
                   d.filename AS filename,
                   d.file_type AS file_type,
                   d.date AS date_extracted,
                   excerpt
            ORDER BY d.date
            """
            
            result = session.run(cypher_query, **params)
            
            # Group by date
            by_date: dict[date, list[TimelineDocument]] = defaultdict(list)
            earliest: date | None = None
            latest: date | None = None
            total = 0
            
            for record in result:
                date_str = record["date_extracted"]
                if not date_str:
                    continue
                
                try:
                    doc_date = datetime.fromisoformat(date_str).date()
                except (ValueError, TypeError):
                    continue
                
                # Track range
                if earliest is None or doc_date < earliest:
                    earliest = doc_date
                if latest is None or doc_date > latest:
                    latest = doc_date
                
                total += 1
                
                excerpt_text = record["excerpt"][:200] if record["excerpt"] else None
                
                by_date[doc_date].append(
                    TimelineDocument(
                        id=record["id"],
                        filename=record["filename"] or "Unknown",
                        file_type=record["file_type"] or "",
                        title=record["filename"] or "Unknown",
                        excerpt=excerpt_text,
                    )
                )
            
            # Convert to timeline entries
            timeline = [
                TimelineEntry(
                    date=d,
                    document_count=len(docs),
                    documents=docs,
                )
                for d, docs in sorted(by_date.items())
            ]
            
            return TimelineResponse(
                timeline=timeline,
                date_range=DateRange(earliest=earliest, latest=latest),
                total_documents=total,
            )

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document and its chunks from Neo4j.

        Args:
            document_id: The document ID to delete

        Returns:
            True if deleted, False if not found
        """
        from uu_backend.database.neo4j_client import get_neo4j_client
        
        neo4j_client = get_neo4j_client()
        neo4j_client.delete_document_graph_data(document_id)
        return True

    def get_document_id_for_chunk(self, chunk_id: str) -> str | None:
        """
        Resolve a document ID from a chunk ID in Neo4j.

        Args:
            chunk_id: Chunk ID

        Returns:
            Document ID if found, otherwise None
        """
        with self._driver.session(database=self._database) as session:
            result = session.run(
                """
                MATCH (c:Chunk {id: $chunk_id})-[:FROM_DOCUMENT]->(d:Document)
                RETURN d.id AS document_id
                """,
                chunk_id=chunk_id
            ).single()
            
            if result:
                return result["document_id"]
            return None

    def count(self) -> int:
        """Get the total number of documents in Neo4j."""
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (d:Document) RETURN count(d) AS count"
            ).single()
            return int(result["count"] or 0)

    def chunk_count(self) -> int:
        """Get the total number of chunks in Neo4j."""
        with self._driver.session(database=self._database) as session:
            result = session.run(
                "MATCH (c:Chunk) RETURN count(c) AS count"
            ).single()
            return int(result["count"] or 0)

    def semantic_search(
        self, 
        query: str, 
        n_results: int = 5,
        document_ids: list[str] | None = None
    ) -> list[dict]:
        """
        Search for documents using semantic similarity via Neo4j vector search.
        
        Args:
            query: The search query
            n_results: Maximum number of results to return
            document_ids: Optional list of document IDs to search within
            
        Returns:
            List of search results with document info and relevance scores
        """
        if document_ids is not None and len(document_ids) == 0:
            return []
        
        # Generate query embedding using OpenAI
        from neo4j_graphrag.embeddings.openai import OpenAIEmbeddings
        settings = get_settings()
        
        if not settings.openai_api_key:
            return []
        
        embedder = OpenAIEmbeddings(
            model=settings.graphrag_embedding_model,
            api_key=settings.openai_api_key,
        )
        query_embedding = embedder.embed_query(query)
        
        with self._driver.session(database=self._database) as session:
            # Use Neo4j vector search
            cypher_query = """
            CALL db.index.vector.queryNodes($index_name, $top_k, $query_vector)
            YIELD node AS chunk, score
            MATCH (chunk)-[:FROM_DOCUMENT]->(d:Document)
            """
            
            # Add document filter if specified
            if document_ids:
                cypher_query += "WHERE d.id IN $document_ids\n"
            
            cypher_query += """
            RETURN chunk.id AS chunk_id,
                   d.id AS document_id,
                   d.filename AS filename,
                   chunk.index AS chunk_index,
                   chunk.text AS content,
                   score AS similarity
            ORDER BY similarity DESC
            LIMIT $top_k
            """
            
            result = session.run(
                cypher_query,
                index_name=settings.graphrag_vector_index_name,
                top_k=n_results,
                query_vector=query_embedding,
                document_ids=document_ids
            )
            
            search_results = []
            for record in result:
                search_results.append({
                    "chunk_id": record["chunk_id"],
                    "document_id": record["document_id"],
                    "filename": record["filename"] or "Unknown",
                    "chunk_index": int(record["chunk_index"] or 0),
                    "content": record["content"] or "",
                    "similarity": float(record["similarity"] or 0.0),
                })
            
            return search_results


# Module-level instance
_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get or create the VectorStore instance."""
    global _store
    if _store is None:
        _store = VectorStore()
    return _store
