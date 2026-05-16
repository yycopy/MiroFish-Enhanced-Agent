"""ORM model for multi-agent claim review results."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, Index, Integer, Text

from ..db import Base


def utc_now() -> datetime:
    """Return a naive UTC timestamp suitable for MySQL DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Review(Base):
    """A persisted review result for one verifiable claim."""

    __tablename__ = "review"
    __table_args__ = (
        Index("idx_review_created_at", "created_at"),
        Index("idx_review_confidence", "confidence_score"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    claim = Column(Text, nullable=False)
    supporting_evidence_json = Column(Text, nullable=True)
    opposing_evidence_json = Column(Text, nullable=True)
    neutral_evidence_json = Column(Text, nullable=True)
    role_reviews_json = Column(Text, nullable=True)
    confidence_score = Column(Float, nullable=False, default=0.0)
    risk_notes_json = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)

    def to_dict(self) -> dict:
        """Convert the ORM row into a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "claim": self.claim,
            "supporting_evidence_json": self.supporting_evidence_json,
            "opposing_evidence_json": self.opposing_evidence_json,
            "neutral_evidence_json": self.neutral_evidence_json,
            "role_reviews_json": self.role_reviews_json,
            "confidence_score": self.confidence_score,
            "risk_notes_json": self.risk_notes_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
