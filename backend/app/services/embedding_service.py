"""Embedding generation for long-term memory retrieval.

This service calls an OpenAI-compatible embeddings endpoint. The enhanced
project requires a real embedding model because semantic recall quality depends
on real vector representations.
"""

from typing import Iterable, List

from openai import OpenAI

from ..config import Config


PLACEHOLDER_KEYS = {"", "your_api_key_here", "your_openai_api_key_here", "your_chat_model_key_here"}


class EmbeddingService:
    """Generate embeddings through an OpenAI-compatible API."""

    def __init__(self, config=Config):
        self.config = config
        self.api_key = (config.OPENAI_API_KEY or "").strip()
        self.base_url = config.OPENAI_BASE_URL
        self.model = (config.EMBEDDING_MODEL or "").strip()
        self._client = None

    def _validate_config(self) -> None:
        """Fail clearly when embedding configuration is incomplete."""
        if not self.model:
            raise RuntimeError("EMBEDDING_MODEL is required for semantic memory recall")
        if self.api_key.lower() in PLACEHOLDER_KEYS:
            raise RuntimeError("OPENAI_API_KEY is required for embedding generation")
        if not self.base_url:
            raise RuntimeError("OPENAI_BASE_URL is required for embedding generation")

    def _get_client(self) -> OpenAI:
        """Create the OpenAI-compatible client lazily."""
        self._validate_config()
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def embed_text(self, text: str) -> List[float]:
        """Embed a single text string."""
        return self.embed_texts([text])[0]

    def embed_texts(self, texts: Iterable[str]) -> List[List[float]]:
        """Embed several texts while preserving input order."""
        prepared = [self._prepare_text(text) for text in texts]
        response = self._get_client().embeddings.create(model=self.model, input=prepared)
        return [item.embedding for item in response.data]

    def _prepare_text(self, text: str) -> str:
        """Normalize empty text because embedding APIs reject blank input."""
        value = (text or "").strip()
        return value if value else "empty memory text"
