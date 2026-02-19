"""OpenAI API client for LLM operations."""

import json
from typing import Any

from openai import OpenAI

from uu_backend.config import get_settings
from uu_backend.llm.options import (
    completion_token_options_for_model,
    reasoning_options_for_model,
)


class OpenAIClient:
    """Client for OpenAI API operations."""

    def __init__(self):
        """Initialize OpenAI client."""
        settings = get_settings()
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

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
