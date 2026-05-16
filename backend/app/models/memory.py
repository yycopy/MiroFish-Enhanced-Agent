"""ORM models for long-term memory.

These tables are intentionally independent from the original graph, simulation,
and report storage. Later phases can write active-search results here first,
then selectively embed them into Chroma or write relations to Zep.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from ..db import Base


def utc_now() -> datetime:
    """Return a naive UTC timestamp suitable for MySQL DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class MemoryItem(Base):
    """A durable text memory item collected or created by enhanced modules."""

    __tablename__ = "memory_item"
    __table_args__ = (
        Index("idx_memory_item_type_time", "memory_type", "publish_time"),
        Index("idx_memory_item_source_type", "source_type"),
        Index("idx_memory_item_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(255), nullable=True)
    source_type = Column(String(64), nullable=True)
    url = Column(String(1024), nullable=True)
    title = Column(String(512), nullable=True)
    raw_text = Column(Text, nullable=True)
    clean_text = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    publish_time = Column(DateTime, nullable=True)
    content_hash = Column(String(64), nullable=True, unique=True, index=True)
    importance_score = Column(Float, nullable=False, default=0.0)
    credibility_score = Column(Float, nullable=False, default=0.0)
    memory_type = Column(String(64), nullable=False, default="general")
    is_embedded = Column(Boolean, nullable=False, default=False)
    is_written_to_zep = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    evidence = relationship(
        "MemoryEvidence",
        back_populates="memory",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def to_dict(self, include_evidence: bool = False) -> dict:
        """Convert the ORM object into a JSON-serializable dictionary."""
        data = {
            "id": self.id,
            "source": self.source,
            "source_type": self.source_type,
            "url": self.url,
            "title": self.title,
            "raw_text": self.raw_text,
            "clean_text": self.clean_text,
            "summary": self.summary,
            "publish_time": self.publish_time.isoformat() if self.publish_time else None,
            "content_hash": self.content_hash,
            "importance_score": self.importance_score,
            "credibility_score": self.credibility_score,
            "memory_type": self.memory_type,
            "is_embedded": self.is_embedded,
            "is_written_to_zep": self.is_written_to_zep,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
        if include_evidence:
            data["evidence"] = [item.to_dict() for item in self.evidence]
        return data


class MemoryEvidence(Base):
    """A claim-evidence slice linked to a memory item."""

    __tablename__ = "memory_evidence"
    __table_args__ = (
        Index("idx_memory_evidence_memory_id", "memory_id"),
        Index("idx_memory_evidence_type", "evidence_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    memory_id = Column(Integer, ForeignKey("memory_item.id", ondelete="CASCADE"), nullable=False)
    claim = Column(Text, nullable=True)
    evidence_text = Column(Text, nullable=True)
    evidence_type = Column(String(64), nullable=True)
    source_url = Column(String(1024), nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    memory = relationship("MemoryItem", back_populates="evidence")

    def to_dict(self) -> dict:
        """Convert the evidence row into a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "memory_id": self.memory_id,
            "claim": self.claim,
            "evidence_text": self.evidence_text,
            "evidence_type": self.evidence_type,
            "source_url": self.source_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
