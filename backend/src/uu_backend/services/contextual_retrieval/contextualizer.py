"""Context generation for chunks using OpenAI with async support."""

import asyncio
import logging
import os
from typing import Callable

from openai import AsyncOpenAI, AsyncAzureOpenAI, OpenAI, AzureOpenAI, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from uu_backend.config import get_settings

from .models import Chunk, ContextualizedChunk

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You are a document analyst. You will be given a document excerpt to reference.

<document_excerpt>
{document}
</document_excerpt>

When given a chunk, respond with ONE brief sentence of context to situate it within the document. Be extremely concise."""

USER_PROMPT = """Provide a short context for this chunk:

<chunk>
{chunk}
</chunk>"""


class ChunkContextualizer:
    """
    Generate context for each chunk using an LLM.
    
    This prepends explanatory context to each chunk before embedding,
    which improves retrieval accuracy by 35% according to Anthropic's research.
    
    Supports both sync and async operations. Async is recommended for batch
    processing as it enables concurrent API calls.
    
    Leverages OpenAI's automatic prompt caching:
    - Document excerpt (static prefix) is cached after first request
    - Subsequent requests with same prefix get 50% cost reduction
    """

    def __init__(
        self,
        model: str | None = None,
        max_completion_tokens: int = 500,
        max_context_chars: int = 25_000,
        max_concurrency: int = 40,  # Optimized for 500K TPM with 4K chunks (~34% utilization)
        api_key: str | None = None,
    ):
        settings = get_settings()
        self.model = model or settings.effective_context_model
        self.max_completion_tokens = max_completion_tokens
        self.max_context_chars = max_context_chars
        self.max_concurrency = int(os.getenv("MAX_CONCURRENCY", str(max_concurrency)))
        
        # Check if using Azure OpenAI or regular OpenAI
        use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"
        
        if use_azure:
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_api_key = api_key or os.getenv("AZURE_OPENAI_API_KEY")
            azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")
            
            if not azure_endpoint or not azure_api_key:
                raise ValueError(
                    "Azure OpenAI enabled but missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY"
                )
            
            logger.info(f"Using Azure OpenAI: {azure_endpoint}")
            self.client = AzureOpenAI(
                api_version=azure_api_version,
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
            )
            self.async_client = AsyncAzureOpenAI(
                api_version=azure_api_version,
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
            )
        else:
            logger.info("Using OpenAI")
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.client = OpenAI(api_key=api_key)
            self.async_client = AsyncOpenAI(api_key=api_key)
        
        self._cached_doc_excerpt: str | None = None
        self._cached_system_prompt: str | None = None
        self._total_cached_tokens = 0
        self._total_prompt_tokens = 0
        self._completed_count = 0

    def _get_document_excerpt(self, document: str) -> str:
        """
        Get document excerpt, cached for reuse across all chunks.
        """
        if self._cached_doc_excerpt is not None:
            return self._cached_doc_excerpt
        
        if len(document) <= self.max_context_chars:
            self._cached_doc_excerpt = document
        else:
            self._cached_doc_excerpt = document[:self.max_context_chars] + "\n\n[Document truncated...]"
        
        return self._cached_doc_excerpt

    def _get_cached_system_prompt(self, document: str) -> str:
        """
        Get the system prompt with document, cached for reuse.
        
        Caching ensures the EXACT same string is sent every time,
        which is required for OpenAI prompt caching to work.
        """
        if self._cached_system_prompt is not None:
            return self._cached_system_prompt
        
        doc_excerpt = self._get_document_excerpt(document)
        self._cached_system_prompt = SYSTEM_PROMPT.format(document=doc_excerpt)
        return self._cached_system_prompt

    def contextualize(self, document: str, chunk: str) -> str:
        """
        Generate context for a single chunk (synchronous).
        """
        system_prompt = self._get_cached_system_prompt(document)
        
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": USER_PROMPT.format(chunk=chunk)},
            ],
            max_completion_tokens=self.max_completion_tokens,
        )
        
        self._track_cache_stats(response.usage)
        return response.choices[0].message.content or ""

    async def acontextualize(
        self,
        document: str,
        chunk: str,
    ) -> str:
        """
        Generate context for a single chunk (asynchronous with retry).
        
        Uses tenacity for exponential backoff on rate limits.
        Uses system message for document (better for caching).
        """
        system_prompt = self._get_cached_system_prompt(document)
        
        @retry(
            retry=retry_if_exception_type(RateLimitError),
            wait=wait_exponential(multiplier=1, min=2, max=60),
            stop=stop_after_attempt(5),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _call_api():
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": USER_PROMPT.format(chunk=chunk)},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            self._track_cache_stats(response.usage)
            return response.choices[0].message.content or ""
        
        return await _call_api()

    def _track_cache_stats(self, usage) -> None:
        """Track cache statistics from API response."""
        if usage:
            self._total_prompt_tokens += usage.prompt_tokens
            if hasattr(usage, 'prompt_tokens_details'):
                details = usage.prompt_tokens_details
                if details and hasattr(details, 'cached_tokens'):
                    self._total_cached_tokens += details.cached_tokens or 0

    def get_cache_stats(self) -> dict:
        """Get cumulative cache statistics."""
        return {
            "total_prompt_tokens": self._total_prompt_tokens,
            "total_cached_tokens": self._total_cached_tokens,
            "cache_hit_rate": (
                self._total_cached_tokens / self._total_prompt_tokens * 100
                if self._total_prompt_tokens > 0 else 0
            ),
        }

    def reset_stats(self) -> None:
        """Reset cache statistics and document cache for a new document."""
        self._total_cached_tokens = 0
        self._total_prompt_tokens = 0
        self._completed_count = 0
        self._cached_doc_excerpt = None
        self._cached_system_prompt = None

    def contextualize_chunk(
        self,
        document: str,
        chunk: Chunk,
    ) -> ContextualizedChunk:
        """Generate context for a chunk (synchronous)."""
        context = self.contextualize(document, chunk.text)
        
        return ContextualizedChunk(
            doc_id=chunk.doc_id,
            index=chunk.index,
            original_text=chunk.text,
            context=context,
            page_summary="",
            contextualized_text=f"{context}\n\n{chunk.text}",
            metadata=chunk.metadata,
        )

    async def acontextualize_chunk(
        self,
        document: str,
        chunk: Chunk,
        semaphore: asyncio.Semaphore,
        progress_callback: Callable[[int, int], None] | None = None,
        total: int = 0,
    ) -> ContextualizedChunk:
        """Generate context for a chunk (asynchronous with semaphore)."""
        async with semaphore:
            context = await self.acontextualize(document, chunk.text)
            
            self._completed_count += 1
            if progress_callback:
                progress_callback(self._completed_count, total)
            
            return ContextualizedChunk(
                doc_id=chunk.doc_id,
                index=chunk.index,
                original_text=chunk.text,
                context=context,
                page_summary="",
                contextualized_text=f"{context}\n\n{chunk.text}",
                metadata=chunk.metadata,
            )

    def contextualize_chunks(
        self,
        document: str,
        chunks: list[Chunk],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[ContextualizedChunk]:
        """
        Contextualize multiple chunks (synchronous, sequential).
        
        For better performance, use contextualize_chunks_async instead.
        """
        contextualized = []
        total = len(chunks)
        
        for i, chunk in enumerate(chunks):
            ctx_chunk = self.contextualize_chunk(document, chunk)
            contextualized.append(ctx_chunk)
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return contextualized

    async def acontextualize_chunks(
        self,
        document: str,
        chunks: list[Chunk],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[ContextualizedChunk]:
        """
        Contextualize multiple chunks concurrently (asynchronous).
        
        Uses a semaphore to limit concurrent requests to max_concurrency.
        This is much faster than sequential processing.
        """
        self._completed_count = 0
        total = len(chunks)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        
        # Pre-cache the document excerpt
        self._get_document_excerpt(document)
        
        tasks = [
            self.acontextualize_chunk(
                document, chunk, semaphore, progress_callback, total
            )
            for chunk in chunks
        ]
        
        results = await asyncio.gather(*tasks)
        
        # Sort by index to maintain original order
        return sorted(results, key=lambda x: x.index)

    def contextualize_chunks_async(
        self,
        document: str,
        chunks: list[Chunk],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[ContextualizedChunk]:
        """
        Sync wrapper for async batch contextualization.
        
        Works in both regular Python and Jupyter notebooks.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None
        
        if loop and loop.is_running():
            # Already in an async context (e.g., Jupyter)
            # Use nest_asyncio if available, otherwise fall back to sync
            try:
                import nest_asyncio
                nest_asyncio.apply()
                return asyncio.run(
                    self.acontextualize_chunks(document, chunks, progress_callback)
                )
            except ImportError:
                # nest_asyncio not available, use thread-based approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.acontextualize_chunks(document, chunks, progress_callback)
                    )
                    return future.result()
        else:
            return asyncio.run(
                self.acontextualize_chunks(document, chunks, progress_callback)
            )
