"""Three-layer de-duplication for active ingestion documents."""

import hashlib
from difflib import SequenceMatcher
from typing import Dict, Iterable, List

from ..config import Config


class DedupService:
    """Remove duplicate documents by url, content hash, and text similarity."""

    def __init__(self, similarity_threshold: float = Config.INGESTION_DEDUP_SIMILARITY_THRESHOLD):
        self.similarity_threshold = similarity_threshold

    def dedup_documents(self, docs: Iterable[Dict]) -> List[Dict]:
        """Return unique documents while preserving input order."""
        seen_urls = set()
        seen_hashes = set()
        kept_texts: List[str] = []
        unique_docs: List[Dict] = []

        for doc in docs:
            url = (doc.get("url") or "").strip()
            if url and url in seen_urls:
                continue

            text = (doc.get("clean_text") or doc.get("raw_text") or "").strip()
            content_hash = self.content_hash(text)
            if content_hash in seen_hashes:
                continue

            if any(self.text_similarity(text, kept) >= self.similarity_threshold for kept in kept_texts):
                continue

            next_doc = dict(doc)
            next_doc["content_hash"] = content_hash
            unique_docs.append(next_doc)
            kept_texts.append(text)
            if url:
                seen_urls.add(url)
            seen_hashes.add(content_hash)

        return unique_docs

    @staticmethod
    def content_hash(text: str) -> str:
        """Build a sha256 hash for exact content de-duplication."""
        normalized = " ".join((text or "").split()).lower()
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def text_similarity(left: str, right: str) -> float:
        """Compute simple overlap similarity with difflib."""
        if not left or not right:
            return 0.0
        return SequenceMatcher(None, left, right).ratio()


def dedup_documents(docs: Iterable[Dict]) -> List[Dict]:
    """Convenience function used by Celery tasks."""
    return DedupService().dedup_documents(docs)
