"""Page summarization for improved retrieval using OpenAI with async support."""

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

from .models import Chunk

logger = logging.getLogger(__name__)


SUMMARY_PROMPT = """Analyze this document page and create a comprehensive summary optimized for semantic search.

Include:
- Main points and key topics on the page
- Tables present (with brief description of what data they contain)
- Visual elements (forms, charts, diagrams, images)
- Key data fields or information visible

Be specific and concrete. Focus on what information is available on this page.
Respond with 2-3 sentences.

<page_content>
{page_content}
</page_content>"""


class PageSummarizer:
    """
    Generate comprehensive summaries for document pages using an LLM.
    
    This creates rich summaries that describe main points, tables, and visual
    elements on each page, improving retrieval accuracy for page-level search.
    
    Supports both sync and async operations. Async is recommended for batch
    processing as it enables concurrent API calls.
    """

    def __init__(
        self,
        model: str = "gpt-5-mini",
        max_completion_tokens: int = 2000,
        max_concurrency: int = 40,
        api_key: str | None = None,
    ):
        self.model = model
        self.max_completion_tokens = max_completion_tokens
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
            
            logger.info(f"Using Azure OpenAI for page summarization: {azure_endpoint}")
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
            logger.info("Using OpenAI for page summarization")
            api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.client = OpenAI(api_key=api_key)
            self.async_client = AsyncOpenAI(api_key=api_key)
        
        self._completed_count = 0

    def summarize(self, page_content: str) -> str:
        """
        Generate summary for a single page (synchronous).
        """
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": SUMMARY_PROMPT.format(page_content=page_content)},
            ],
            max_completion_tokens=self.max_completion_tokens,
        )
        
        return response.choices[0].message.content or ""

    async def asummarize(self, page_content: str) -> str:
        """
        Generate summary for a single page (asynchronous with retry).
        
        Uses tenacity for exponential backoff on rate limits.
        """
        @retry(
            retry=retry_if_exception_type(RateLimitError),
            wait=wait_exponential(multiplier=1, min=2, max=60),
            stop=stop_after_attempt(5),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )
        async def _call_api():
            prompt = SUMMARY_PROMPT.format(page_content=page_content)
            logger.info(f"Requesting page summary for content ({len(page_content)} chars)")
            logger.info(f"Prompt length: {len(prompt)} chars")
            
            response = await self.async_client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            
            # Debug the response
            choice = response.choices[0]
            logger.info(f"Response finish_reason: {choice.finish_reason}")
            logger.info(f"Response message: {choice.message}")
            logger.info(f"Response content type: {type(choice.message.content)}")
            logger.info(f"Response content value: {repr(choice.message.content)}")
            
            summary = choice.message.content or ""
            logger.info(f"Generated page summary ({len(summary)} chars): {summary[:300] if summary else '(EMPTY)'}")
            return summary
        
        return await _call_api()

    def summarize_page(self, chunk: Chunk) -> str:
        """Generate summary for a page chunk (synchronous)."""
        return self.summarize(chunk.text)

    async def asummarize_page(
        self,
        chunk: Chunk,
        semaphore: asyncio.Semaphore,
        progress_callback: Callable[[int, int], None] | None = None,
        total: int = 0,
    ) -> str:
        """Generate summary for a page chunk (asynchronous with semaphore)."""
        async with semaphore:
            summary = await self.asummarize(chunk.text)
            
            self._completed_count += 1
            if progress_callback:
                progress_callback(self._completed_count, total)
            
            return summary

    def summarize_pages(
        self,
        chunks: list[Chunk],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[str]:
        """
        Summarize multiple pages (synchronous, sequential).
        
        For better performance, use summarize_pages_async instead.
        """
        summaries = []
        total = len(chunks)
        
        for i, chunk in enumerate(chunks):
            summary = self.summarize_page(chunk)
            summaries.append(summary)
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return summaries

    async def asummarize_pages(
        self,
        chunks: list[Chunk],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[str]:
        """
        Summarize multiple pages concurrently (asynchronous).
        
        Uses a semaphore to limit concurrent requests to max_concurrency.
        This is much faster than sequential processing.
        """
        self._completed_count = 0
        total = len(chunks)
        semaphore = asyncio.Semaphore(self.max_concurrency)
        
        tasks = [
            self.asummarize_page(chunk, semaphore, progress_callback, total)
            for chunk in chunks
        ]
        
        return await asyncio.gather(*tasks)

    def summarize_pages_async(
        self,
        chunks: list[Chunk],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[str]:
        """
        Sync wrapper for async batch summarization.
        
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
                    self.asummarize_pages(chunks, progress_callback)
                )
            except ImportError:
                # nest_asyncio not available, use thread-based approach
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.asummarize_pages(chunks, progress_callback)
                    )
                    return future.result()
        else:
            return asyncio.run(
                self.asummarize_pages(chunks, progress_callback)
            )
