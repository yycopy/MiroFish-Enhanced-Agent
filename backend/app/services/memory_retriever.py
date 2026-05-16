"""Semantic recall for long-term memory."""

import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..config import Config
from ..repositories.memory_repository import MemoryRepository
from .memory_store import MemoryStore


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO datetime value from MySQL or Chroma metadata."""
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _clamp_score(value: Any, default: float = 0.0) -> float:
    """Clamp numeric scores to 0..1 and accept 0..100 inputs defensively."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number > 1.0:
        number = number / 100.0
    return max(0.0, min(1.0, number))


def semantic_score_from_distance(distance: Any) -> float:
    """Convert Chroma cosine distance into a 0..1 similarity score."""
    try:
        value = float(distance)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, 1.0 - value))


def time_decay_score(publish_time: Any, *, half_life_days: Optional[float] = None) -> float:
    """Score recent memories higher with exponential time decay."""
    parsed = _parse_datetime(publish_time)
    if parsed is None:
        return 0.5

    half_life = float(half_life_days or Config.MEMORY_TIME_DECAY_HALF_LIFE_DAYS)
    if half_life <= 0:
        return 1.0

    age_days = max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds() / 86400.0)
    return math.exp(-age_days / half_life)


class MemoryRetriever:
    """Recall MySQL memory items through Chroma candidates and reranking."""

    def __init__(
        self,
        *,
        config=Config,
        store: Optional[MemoryStore] = None,
        repository: Optional[MemoryRepository] = None,
    ):
        self.config = config
        self.store = store or MemoryStore(config=config)
        self.repository = repository or MemoryRepository()

    def recall_memory(self, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Recall memories and rerank by semantic, importance, and time scores."""
        question = (question or "").strip()
        if not question:
            raise ValueError("question is required")

        top_k = max(1, min(int(top_k), 50))
        candidate_count = max(top_k, int(self.config.MEMORY_RECALL_CANDIDATES))
        query_result = self.store.query(question, candidate_count)

        ranked: List[Dict[str, Any]] = []
        for candidate in self._flatten_chroma_result(query_result):
            metadata = candidate["metadata"]
            mysql_id = metadata.get("mysql_id")
            if mysql_id is None:
                continue

            item = self.repository.get_item(int(mysql_id))
            if item is None:
                continue

            semantic_score = semantic_score_from_distance(candidate.get("distance"))
            importance_score = _clamp_score(item.get("importance_score"))
            decay_score = time_decay_score(
                item.get("publish_time") or item.get("created_at"),
                half_life_days=self.config.MEMORY_TIME_DECAY_HALF_LIFE_DAYS,
            )
            final_score = (
                semantic_score * float(self.config.MEMORY_RECALL_SEMANTIC_WEIGHT)
                + importance_score * float(self.config.MEMORY_RECALL_IMPORTANCE_WEIGHT)
                + decay_score * float(self.config.MEMORY_RECALL_TIME_DECAY_WEIGHT)
            )

            ranked.append(
                {
                    "id": item.get("id"),
                    "summary": item.get("summary") or item.get("clean_text") or candidate.get("document"),
                    "source": item.get("source"),
                    "url": item.get("url"),
                    "publish_time": item.get("publish_time"),
                    "importance_score": importance_score,
                    "memory_type": item.get("memory_type"),
                    "semantic_score": semantic_score,
                    "time_decay_score": decay_score,
                    "final_score": final_score,
                    "chroma_distance": candidate.get("distance"),
                }
            )

        ranked.sort(key=lambda item: item["final_score"], reverse=True)
        return ranked[:top_k]

    def _flatten_chroma_result(self, query_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Convert Chroma's nested query response into simple candidates."""
        metadatas = (query_result.get("metadatas") or [[]])[0]
        documents = (query_result.get("documents") or [[]])[0]
        distances = (query_result.get("distances") or [[]])[0]

        candidates = []
        for index, metadata in enumerate(metadatas):
            candidates.append(
                {
                    "metadata": metadata or {},
                    "document": documents[index] if index < len(documents) else "",
                    "distance": distances[index] if index < len(distances) else None,
                }
            )
        return candidates


def recall_memory(question: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Convenience function required by the phase 3 interface."""
    return MemoryRetriever().recall_memory(question, top_k=top_k)
