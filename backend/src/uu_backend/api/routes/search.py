"""Search and Q&A API routes."""

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from uu_backend.services.qa_service import get_qa_service

router = APIRouter()


class SearchResult(BaseModel):
    """A single search result."""
    
    document_id: str
    filename: str
    chunk_index: int
    content: str
    similarity: float


class SearchResponse(BaseModel):
    """Response for semantic search."""
    
    query: str
    results: list[SearchResult]
    total: int


class QuestionRequest(BaseModel):
    """Request for Q&A."""
    
    question: str = Field(..., min_length=1, description="The question to answer")
    document_ids: Optional[list[str]] = Field(None, description="Optional list of document IDs to search")
    n_context: int = Field(5, ge=1, le=20, description="Number of context chunks to use")


class QuestionSource(BaseModel):
    """A source used for answering a question."""
    
    document_id: str
    filename: str
    chunk_index: int
    similarity: float
    excerpt: str


class QuestionResponse(BaseModel):
    """Response for Q&A."""
    
    question: str
    answer: str
    confidence: float
    sources: list[QuestionSource]
    referenced_sources: list[int] = []


@router.get("/search", response_model=SearchResponse)
async def semantic_search(
    q: str = Query(..., min_length=1, description="Search query"),
    n_results: int = Query(5, ge=1, le=50, description="Number of results"),
    document_ids: Optional[str] = Query(None, description="Comma-separated document IDs to filter"),
):
    """
    Perform semantic search over document chunks.
    
    Uses vector embeddings to find the most relevant chunks for the query.
    """
    service = get_qa_service()
    
    # Parse document IDs if provided
    doc_ids = None
    if document_ids:
        doc_ids = [d.strip() for d in document_ids.split(",") if d.strip()]
    
    results = service.semantic_search(q, n_results, doc_ids)
    
    return SearchResponse(
        query=q,
        results=[
            SearchResult(
                document_id=r["document_id"],
                filename=r["filename"],
                chunk_index=r["chunk_index"],
                content=r["content"],
                similarity=r["similarity"],
            )
            for r in results
        ],
        total=len(results),
    )


@router.post("/ask", response_model=QuestionResponse)
async def ask_question(request: QuestionRequest):
    """
    Answer a question using RAG (Retrieval-Augmented Generation).
    
    This endpoint:
    1. Searches for relevant document chunks using semantic search
    2. Uses an LLM to generate an answer based on the retrieved context
    3. Returns the answer along with source citations
    """
    service = get_qa_service()
    
    result = service.ask(
        question=request.question,
        document_ids=request.document_ids,
        n_context=request.n_context,
    )
    
    return QuestionResponse(
        question=request.question,
        answer=result["answer"],
        confidence=result["confidence"],
        sources=[
            QuestionSource(
                document_id=s["document_id"],
                filename=s["filename"],
                chunk_index=s["chunk_index"],
                similarity=s["similarity"],
                excerpt=s["excerpt"],
            )
            for s in result["sources"]
        ],
        referenced_sources=result.get("referenced_sources", []),
    )
