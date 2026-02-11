"""Question-answering service using RAG (Retrieval-Augmented Generation)."""

from typing import Optional

from openai import OpenAI

from uu_backend.database.vector_store import get_vector_store
from uu_backend.llm.options import reasoning_options_for_model


class QAService:
    """Service for answering questions about documents using RAG."""

    def __init__(self):
        self.client = OpenAI()
        self.model = "gpt-5-mini"

    def semantic_search(
        self,
        query: str,
        n_results: int = 5,
        document_ids: Optional[list[str]] = None
    ) -> list[dict]:
        """
        Search for relevant document chunks.
        
        Args:
            query: The search query
            n_results: Maximum number of results
            document_ids: Optional filter to specific documents
            
        Returns:
            List of search results with content and metadata
        """
        vector_store = get_vector_store()
        return vector_store.semantic_search(query, n_results, document_ids)

    def ask(
        self,
        question: str,
        document_ids: Optional[list[str]] = None,
        n_context: int = 5
    ) -> dict:
        """
        Answer a question using RAG (Retrieval-Augmented Generation).
        
        Args:
            question: The question to answer
            document_ids: Optional list of document IDs to search within
            n_context: Number of context chunks to retrieve
            
        Returns:
            Dictionary with answer, sources, and confidence
        """
        # Step 1: Retrieve relevant context
        search_results = self.semantic_search(question, n_context, document_ids)
        
        if not search_results:
            return {
                "answer": "I couldn't find any relevant documents to answer your question.",
                "sources": [],
                "confidence": 0.0,
            }
        
        # Step 2: Build context from search results
        context_parts = []
        sources = []
        
        for i, result in enumerate(search_results):
            context_parts.append(f"[Source {i+1}: {result['filename']}]\n{result['content']}")
            sources.append({
                "document_id": result["document_id"],
                "filename": result["filename"],
                "chunk_index": result["chunk_index"],
                "similarity": result["similarity"],
                "excerpt": result["content"][:200] + "..." if len(result["content"]) > 200 else result["content"],
            })
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Step 3: Generate answer using LLM
        system_prompt = """You are a helpful document assistant. Answer the user's question based ONLY on the provided context.

Guidelines:
- If the answer is clearly in the context, provide it with confidence
- If the answer is partially in the context, provide what you can and note what's missing
- If the answer is NOT in the context, clearly state that you couldn't find the information
- Reference which source(s) you used in your answer
- Be concise but complete

Respond in JSON format:
{
    "answer": "Your answer to the question",
    "confidence": 0.0-1.0 based on how well the context supports your answer,
    "referenced_sources": [1, 2] // list of source numbers you used
}
"""

        user_prompt = f"""## Context from Documents

{context}

## Question

{question}

Please answer the question based on the context above."""

        print(f"\n{'='*60}")
        print("Q&A QUERY")
        print(f"{'='*60}")
        print(f"Question: {question}")
        print(f"Context sources: {len(search_results)}")
        print(f"{'='*60}\n")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"},
                **reasoning_options_for_model(self.model),
            )
            
            import json
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            print(f"Answer: {result.get('answer', '')[:200]}...")
            
            return {
                "answer": result.get("answer", ""),
                "confidence": result.get("confidence", 0.5),
                "sources": sources,
                "referenced_sources": result.get("referenced_sources", []),
            }
            
        except Exception as e:
            print(f"Q&A error: {e}")
            return {
                "answer": f"An error occurred while generating the answer: {str(e)}",
                "sources": sources,
                "confidence": 0.0,
            }


# Singleton instance
_qa_service: Optional[QAService] = None


def get_qa_service() -> QAService:
    """Get or create the QA service singleton."""
    global _qa_service
    if _qa_service is None:
        _qa_service = QAService()
    return _qa_service
