"""OpenAI API client for LLM operations."""

import json
import logging
import os
from typing import Any

from openai import AzureOpenAI, OpenAI

from uu_backend.config import get_settings
from uu_backend.llm.options import (
    completion_token_options_for_model,
    reasoning_options_for_model,
)

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Client for OpenAI API operations. Supports both OpenAI and Azure OpenAI."""

    def __init__(self):
        """Initialize OpenAI client."""
        settings = get_settings()
        self._model = settings.openai_model

        # Check if using Azure OpenAI or regular OpenAI
        use_azure = os.getenv("USE_AZURE_OPENAI", "false").lower() == "true"

        logger.info(f"[OpenAIClient] USE_AZURE_OPENAI={use_azure}")

        if use_azure:
            azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            azure_api_key = os.getenv("AZURE_OPENAI_API_KEY")
            azure_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview")

            logger.info(f"[OpenAIClient] Azure endpoint: {azure_endpoint}")
            logger.info(f"[OpenAIClient] Azure key present: {bool(azure_api_key)}")

            if not azure_endpoint or not azure_api_key:
                raise ValueError(
                    "Azure OpenAI enabled but missing AZURE_OPENAI_ENDPOINT or AZURE_OPENAI_API_KEY"
                )

            logger.info(f"[OpenAIClient] Using Azure OpenAI: {azure_endpoint}")
            self._client = AzureOpenAI(
                api_version=azure_api_version,
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
            )
        else:
            logger.info("[OpenAIClient] Using OpenAI")
            self._client = OpenAI(api_key=settings.openai_api_key)

    def complete(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_completion_tokens: int = 20_000,
    ) -> str:
        """Generate a completion from the model."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            **completion_token_options_for_model(self._model, max_completion_tokens),
            **reasoning_options_for_model(self._model),
        )

        return response.choices[0].message.content or ""

    def complete_json(
        self,
        prompt: str,
        system_prompt: str | None = None,
        max_completion_tokens: int = 4000,
    ) -> dict[str, Any]:
        """Generate a JSON completion from the model."""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            **completion_token_options_for_model(self._model, max_completion_tokens),
            response_format={"type": "json_object"},
            **reasoning_options_for_model(self._model),
        )

        content = response.choices[0].message.content or "{}"
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            raise ValueError("Model returned invalid JSON content")

    def is_available(self) -> bool:
        """Check if OpenAI API is available."""
        settings = get_settings()
        return bool(settings.openai_api_key)


# Module-level instance
_client: OpenAIClient | None = None


def get_openai_client() -> OpenAIClient:
    """Get or create the OpenAI client instance."""
    global _client
    if _client is None:
        _client = OpenAIClient()
    return _client
