"""Text cleaning for active ingestion documents."""

import html
import re
from typing import Dict, Iterable, List

from ..config import Config


TAG_PATTERN = re.compile(r"<[^>]+>")
SPACE_PATTERN = re.compile(r"\s+")


class ContentCleaner:
    """Clean raw documents before summarization and de-duplication."""

    def __init__(self, min_length: int = Config.INGESTION_CONTENT_MIN_LENGTH):
        self.min_length = min_length

    def clean_documents(self, raw_docs: Iterable[Dict]) -> List[Dict]:
        """Clean many documents and drop very short results."""
        cleaned = []
        for doc in raw_docs:
            clean_text = self.clean_text(doc.get("raw_text") or "")
            if len(clean_text) < self.min_length:
                continue
            next_doc = dict(doc)
            next_doc["clean_text"] = clean_text
            cleaned.append(next_doc)
        return cleaned

    def clean_text(self, raw_text: str) -> str:
        """Remove html tags, unescape entities, and normalize whitespace."""
        text = html.unescape(raw_text or "")
        text = TAG_PATTERN.sub(" ", text)
        text = SPACE_PATTERN.sub(" ", text)
        return text.strip()


def clean_documents(raw_docs: Iterable[Dict]) -> List[Dict]:
    """Convenience function used by Celery tasks."""
    return ContentCleaner().clean_documents(raw_docs)
