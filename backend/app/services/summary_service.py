"""Summary compression for active ingestion documents."""

import json
import re
from typing import Any, Dict

from openai import OpenAI

from ..config import Config


PLACEHOLDER_KEYS = {"", "your_api_key_here", "your_openai_api_key_here", "your_chat_model_key_here"}


class SummaryService:
    """Compress cleaned text into structured memory fields with a real LLM."""

    def __init__(self, config=Config):
        self.config = config
        self.api_key = (config.OPENAI_API_KEY or config.LLM_API_KEY or "").strip()
        self.base_url = config.OPENAI_BASE_URL or config.LLM_BASE_URL
        self.model = config.OPENAI_MODEL or config.LLM_MODEL_NAME
        self._client = None

    def summarize_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Return summary, entities, events, opinions, evidence, and uncertainty."""
        clean_text = (doc.get("clean_text") or "").strip()
        if not clean_text:
            raise ValueError("clean_text is required for summarization")
        self._validate_config()
        return self._llm_summary(doc)

    def _validate_config(self) -> None:
        """Fail clearly when LLM configuration is incomplete."""
        if self.api_key.lower() in PLACEHOLDER_KEYS:
            raise RuntimeError("OPENAI_API_KEY or LLM_API_KEY is required for summarization")
        if not self.base_url:
            raise RuntimeError("OPENAI_BASE_URL or LLM_BASE_URL is required for summarization")
        if not self.model:
            raise RuntimeError("OPENAI_MODEL or LLM_MODEL_NAME is required for summarization")

    def _llm_summary(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Call an OpenAI-compatible chat model and parse JSON output."""
        text = (doc.get("clean_text") or "")[: self.config.SUMMARY_MAX_INPUT_CHARS]
        prompt = (
            "Compress the following text into strict JSON. Do not output markdown. "
            "Required fields: summary, entities, events, opinions, evidence, uncertainty. "
            "entities/events/opinions/evidence must be arrays; uncertainty must be a string.\n\n"
            f"title: {doc.get('title') or ''}\n"
            f"source: {doc.get('source') or ''}\n"
            f"text: {text}"
        )
        response = self._get_client().chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are an information compression assistant. Output valid JSON only."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
        )
        content = response.choices[0].message.content or "{}"
        return self._normalize_summary(json.loads(self._strip_code_fence(content)), doc)

    def _normalize_summary(self, value: Dict[str, Any], doc: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure every required field exists with predictable types."""
        return {
            "summary": str(value.get("summary") or doc.get("clean_text") or "")[:500],
            "entities": self._list_value(value.get("entities")),
            "events": self._list_value(value.get("events")),
            "opinions": self._list_value(value.get("opinions")),
            "evidence": self._list_value(value.get("evidence")),
            "uncertainty": str(value.get("uncertainty") or ""),
        }

    def _get_client(self) -> OpenAI:
        """Create the OpenAI-compatible client lazily."""
        self._validate_config()
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    @staticmethod
    def _strip_code_fence(text: str) -> str:
        """Remove common JSON code fences from model output."""
        value = text.strip()
        if value.startswith("```"):
            value = re.sub(r"^```(?:json)?", "", value).strip()
            value = re.sub(r"```$", "", value).strip()
        return value

    @staticmethod
    def _list_value(value: Any) -> list:
        """Normalize scalar or list values into a list."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]


def summarize_document(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function used by Celery tasks."""
    return SummaryService().summarize_document(doc)
