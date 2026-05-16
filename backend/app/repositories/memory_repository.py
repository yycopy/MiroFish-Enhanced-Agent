"""Repository methods for long-term memory items and evidence."""

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, or_, select

from ..db import create_all_tables, session_scope
from ..models.memory import MemoryEvidence, MemoryItem


def _parse_datetime(value: Any) -> Optional[datetime]:
    """Parse an ISO datetime string while accepting empty values."""
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    raise ValueError("publish_time must be an ISO datetime string")


def _float_or_default(value: Any, default: float = 0.0) -> float:
    """Convert numeric input to float and keep API defaults predictable."""
    if value is None or value == "":
        return default
    return float(value)


def _bool_or_default(value: Any, default: bool = False) -> bool:
    """Convert common JSON values to boolean."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def build_content_hash(data: Dict[str, Any]) -> str:
    """Build a stable sha256 hash for de-duplication."""
    text = "\n".join(
        str(data.get(key) or "")
        for key in ["source", "source_type", "url", "title", "clean_text", "raw_text", "summary"]
    )
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class MemoryRepository:
    """Encapsulates CRUD access to memory_item and memory_evidence."""

    def ensure_schema(self) -> None:
        """Create memory tables if the configured MySQL database is reachable."""
        create_all_tables()

    def create_item(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert one memory item and return it as a dictionary."""
        payload = dict(data)
        payload.setdefault("content_hash", build_content_hash(payload))

        item = MemoryItem(
            source=payload.get("source"),
            source_type=payload.get("source_type"),
            url=payload.get("url"),
            title=payload.get("title"),
            raw_text=payload.get("raw_text"),
            clean_text=payload.get("clean_text"),
            summary=payload.get("summary"),
            publish_time=_parse_datetime(payload.get("publish_time")),
            content_hash=payload.get("content_hash"),
            importance_score=_float_or_default(payload.get("importance_score")),
            credibility_score=_float_or_default(payload.get("credibility_score")),
            memory_type=payload.get("memory_type") or "general",
            is_embedded=_bool_or_default(payload.get("is_embedded")),
            is_written_to_zep=_bool_or_default(payload.get("is_written_to_zep")),
        )

        with session_scope() as session:
            session.add(item)
            session.flush()
            return item.to_dict(include_evidence=True)

    def list_items(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        memory_type: Optional[str] = None,
        source_type: Optional[str] = None,
        keyword: Optional[str] = None,
        min_importance: Optional[float] = None,
        only_not_in_zep: bool = False,
    ) -> List[Dict[str, Any]]:
        """List memory items with simple filters and pagination."""
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))

        statement = select(MemoryItem).order_by(MemoryItem.created_at.desc())
        if memory_type:
            statement = statement.where(MemoryItem.memory_type == memory_type)
        if source_type:
            statement = statement.where(MemoryItem.source_type == source_type)
        if keyword:
            kw = f"%{keyword}%"
            statement = statement.where(
                or_(
                    MemoryItem.title.like(kw),
                    MemoryItem.summary.like(kw),
                    MemoryItem.clean_text.like(kw),
                )
            )
        if min_importance is not None:
            statement = statement.where(MemoryItem.importance_score >= min_importance)
        if only_not_in_zep:
            statement = statement.where(MemoryItem.is_written_to_zep == False)  # noqa: E712
        statement = statement.limit(limit).offset(offset)

        with session_scope() as session:
            rows = session.execute(statement).scalars().all()
            return [item.to_dict(include_evidence=False) for item in rows]

    def get_item(self, item_id: int) -> Optional[Dict[str, Any]]:
        """Get one memory item by primary key."""
        with session_scope() as session:
            item = session.get(MemoryItem, int(item_id))
            if item is None:
                return None
            return item.to_dict(include_evidence=True)

    def delete_item(self, item_id: int) -> bool:
        """Delete one memory item and its evidence rows."""
        with session_scope() as session:
            item = session.get(MemoryItem, int(item_id))
            if item is None:
                return False
            session.delete(item)
            return True

    def mark_embedded(self, item_id: int, is_embedded: bool = True) -> Optional[Dict[str, Any]]:
        """Update the Chroma embedding flag for one memory item."""
        with session_scope() as session:
            item = session.get(MemoryItem, int(item_id))
            if item is None:
                return None
            item.is_embedded = is_embedded
            session.flush()
            return item.to_dict(include_evidence=False)

    def mark_written_to_zep(self, item_id: int, is_written_to_zep: bool = True) -> Optional[Dict[str, Any]]:
        """Update the Zep graph-memory flag for one memory item."""
        with session_scope() as session:
            item = session.get(MemoryItem, int(item_id))
            if item is None:
                return None
            item.is_written_to_zep = is_written_to_zep
            session.flush()
            return item.to_dict(include_evidence=False)

    def create_evidence(self, memory_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert one evidence slice for a memory item."""
        evidence = MemoryEvidence(
            memory_id=int(memory_id),
            claim=data.get("claim"),
            evidence_text=data.get("evidence_text"),
            evidence_type=data.get("evidence_type"),
            source_url=data.get("source_url"),
        )

        with session_scope() as session:
            session.add(evidence)
            session.flush()
            return evidence.to_dict()
