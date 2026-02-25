"""Page summarization for improved retrieval using OpenAI with async support."""

import asyncio
import logging
import os
from collections.abc import Callable

from openai import AsyncAzureOpenAI, AsyncOpenAI, AzureOpenAI, OpenAI, RateLimitError
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from uu_backend.config import get_settings

from .models import Chunk

logger = logging.getLogger(__name__)


SUMMARY_PROMPT = (
    "Analyze this document page and create a comprehensive summary optimized for "
    "semantic search.\n\n"
    "Include:\n"
    "- Main points and key topics on the page\n"
    "- Tables present (with brief description of what data they contain)\n"
    "- Visual elements (forms, charts, diagrams, images)\n"
    "- Key data fields or information visible\n\n"
    "Be specific and concrete. Focus on what information is available on this page.\n"
    "Respond with 2-3 sentences.\n\n"
    "<page_content>\n"
    "{page_content}\n"
    "</page_content>"
)


class PageSummarizer:
    def __init__(
        self,
        model: str | None = None,
        max_completion_tokens: int = 2000,
        max_concurrency: int = 40,
        api_key: str | None = None,
    ):
        settings = get_settings()
        self.model = model or settings.effective_summary_model
        self.max_completion_tokens = max_completion_tokens
        self.max_concurrency = int(os.getenv("MAX_CONCURRENCY", str(max_concurrency)))

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
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": SUMMARY_PROMPT.format(page_content=page_content)},
            ],
            max_completion_tokens=self.max_completion_tokens,
        )

        return response.choices[0].message.content or ""

    async def asummarize(self, page_content: str) -> str:
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
                    {"role": "user", "content": SUMMARY_PROMPT.format(page_content=page_content)},
                ],
                max_completion_tokens=self.max_completion_tokens,
            )
            return response.choices[0].message.content or ""

        return await _call_api()

    def summarize_page(self, chunk: Chunk) -> str:
        return self.summarize(chunk.text)

    async def asummarize_page(
        self,
        chunk: Chunk,
        semaphore: asyncio.Semaphore,
        progress_callback: Callable[[int, int], None] | None = None,
        total: int = 0,
    ) -> str:
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
        self._completed_count = 0
        total = len(chunks)
        semaphore = asyncio.Semaphore(self.max_concurrency)

        tasks = [
            self.asummarize_page(chunk, semaphore, progress_callback, total) for chunk in chunks
        ]

        return await asyncio.gather(*tasks)

    def summarize_pages_async(
        self,
        chunks: list[Chunk],
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[str]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            try:
                import nest_asyncio

                nest_asyncio.apply()
                return asyncio.run(self.asummarize_pages(chunks, progress_callback))
            except ImportError:
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self.asummarize_pages(chunks, progress_callback)
                    )
                    return future.result()
        else:
            return asyncio.run(self.asummarize_pages(chunks, progress_callback))
