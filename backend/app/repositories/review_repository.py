"""Repository for persisted multi-agent review results."""

import json
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..db import create_all_tables, session_scope
from ..models.review import Review


class ReviewRepository:
    """Encapsulates CRUD access to review rows."""

    def ensure_schema(self) -> None:
        """Create review table if the configured MySQL database is reachable."""
        create_all_tables()

    def create_review(
        self,
        *,
        claim: str,
        evidence_slices: Dict[str, List[Dict[str, Any]]],
        role_reviews: List[Dict[str, Any]],
        confidence_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Persist one review result."""
        row = Review(
            claim=claim,
            supporting_evidence_json=self._dumps(evidence_slices.get("supporting_evidence", [])),
            opposing_evidence_json=self._dumps(evidence_slices.get("opposing_evidence", [])),
            neutral_evidence_json=self._dumps(evidence_slices.get("neutral_evidence", [])),
            role_reviews_json=self._dumps(role_reviews),
            confidence_score=float(confidence_result.get("confidence_score") or 0.0),
            risk_notes_json=self._dumps(confidence_result.get("risk_notes", [])),
        )

        with session_scope() as session:
            session.add(row)
            session.flush()
            return self._row_to_public_dict(row)

    def get_review(self, review_id: int) -> Optional[Dict[str, Any]]:
        """Get one review result by primary key."""
        with session_scope() as session:
            row = session.get(Review, int(review_id))
            if row is None:
                return None
            return self._row_to_public_dict(row)

    def list_reviews(self, *, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """List recent review rows."""
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        statement = select(Review).order_by(Review.created_at.desc()).limit(limit).offset(offset)

        with session_scope() as session:
            rows = session.execute(statement).scalars().all()
            return [self._row_to_public_dict(row) for row in rows]

    def _row_to_public_dict(self, row: Review) -> Dict[str, Any]:
        """Return parsed JSON fields instead of raw JSON strings."""
        return {
            "id": row.id,
            "claim": row.claim,
            "supporting_evidence": self._loads(row.supporting_evidence_json),
            "opposing_evidence": self._loads(row.opposing_evidence_json),
            "neutral_evidence": self._loads(row.neutral_evidence_json),
            "role_reviews": self._loads(row.role_reviews_json),
            "confidence_score": row.confidence_score,
            "risk_notes": self._loads(row.risk_notes_json),
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    @staticmethod
    def _dumps(value: Any) -> str:
        """Serialize JSON safely for a Text column."""
        return json.dumps(value or [], ensure_ascii=False)

    @staticmethod
    def _loads(value: Optional[str]) -> Any:
        """Parse JSON Text columns and return an empty list on missing value."""
        if not value:
            return []
        return json.loads(value)
