"""OpenAI embeddings for contextual retrieval."""

import logging
import os
from collections.abc import Sequence

from openai import AzureOpenAI, OpenAI

logger = logging.getLogger(__name__)


class OpenAIEmbedder:
    """
    Generate embeddings using OpenAI's embedding models.

    Default model is text-embedding-3-small which offers good performance
    at lower cost. Use text-embedding-3-large for higher quality.

    Supports both OpenAI and Azure OpenAI.
    """

    def __init__(
        self,
        model: str = "text-embedding-3-small",
        api_key: str | None = None,
        batch_size: int = 100,
    ):
        self.model = model
        self.batch_size = batch_size

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

            logger.info(f"Using Azure OpenAI for embeddings: {azure_endpoint}")
            self.client = AzureOpenAI(
                api_version=azure_api_version,
                azure_endpoint=azure_endpoint,
                api_key=azure_api_key,
            )
        else:
            logger.info("Using OpenAI for embeddings")
            self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"))

        self._dimensions = {
            "text-embedding-3-small": 1536,
            "text-embedding-3-large": 3072,
            "text-embedding-ada-002": 1536,
        }

    @property
    def dimensions(self) -> int:
        """Return the embedding dimensions for the current model."""
        return self._dimensions.get(self.model, 1536)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Generate embeddings for a list of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        all_embeddings = []

        for i in range(0, len(texts), self.batch_size):
            batch = list(texts[i : i + self.batch_size])

            response = self.client.embeddings.create(
                model=self.model,
                input=batch,
            )

            batch_embeddings = [item.embedding for item in response.data]
            all_embeddings.extend(batch_embeddings)

        return all_embeddings

    def embed_single(self, text: str) -> list[float]:
        """
        Generate embedding for a single text.

        Args:
            text: Text string to embed

        Returns:
            Embedding vector
        """
        embeddings = self.embed([text])
        return embeddings[0] if embeddings else []

    def embed_query(self, query: str) -> list[float]:
        """
        Generate embedding for a search query.

        This is an alias for embed_single, but could be customized
        for query-specific embedding if needed.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        return self.embed_single(query)
