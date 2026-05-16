"""Aggregate independent role reviews into one confidence score."""

from collections import Counter
from typing import Any, Dict, List


class ConfidenceScorer:
    """Calculate confidence, risk level, and final judgement."""

    def calculate_confidence(
        self,
        role_reviews: List[Dict[str, Any]],
        evidence_slices: Dict[str, List[Dict[str, Any]]] | None = None,
    ) -> Dict[str, Any]:
        """Aggregate role decisions and evidence strength."""
        evidence_slices = evidence_slices or {}
        decisions = [review.get("support_decision", "uncertain") for review in role_reviews]
        decision_counts = Counter(decisions)

        avg_role_confidence = self._average([review.get("confidence", 0.5) for review in role_reviews])
        support_strength = min(1.0, 0.18 * len(evidence_slices.get("supporting_evidence", [])))
        oppose_strength = min(1.0, 0.2 * len(evidence_slices.get("opposing_evidence", [])))
        risk_notes = self._collect_risk_notes(role_reviews, evidence_slices)
        risk_penalty = min(0.45, 0.08 * len(risk_notes) + 0.25 * oppose_strength)
        consistency = self._role_consistency(decisions)

        confidence_score = (
            avg_role_confidence * 0.35
            + support_strength * 0.25
            + consistency * 0.25
            + max(0.0, 1.0 - risk_penalty) * 0.15
        )
        confidence_score = max(0.0, min(1.0, round(confidence_score, 4)))

        final_judgement = self._final_judgement(decision_counts, confidence_score, oppose_strength)
        risk_level = self._risk_level(confidence_score, risk_notes, oppose_strength)

        return {
            "confidence_score": confidence_score,
            "risk_level": risk_level,
            "final_judgement": final_judgement,
            "risk_notes": risk_notes,
            "decision_counts": dict(decision_counts),
            "support_strength": round(support_strength, 4),
            "opposing_strength": round(oppose_strength, 4),
            "role_consistency": round(consistency, 4),
        }

    @staticmethod
    def _average(values: List[Any]) -> float:
        """Average numeric values with safe fallback."""
        numbers = []
        for value in values:
            try:
                numbers.append(float(value))
            except (TypeError, ValueError):
                pass
        if not numbers:
            return 0.5
        return sum(numbers) / len(numbers)

    @staticmethod
    def _role_consistency(decisions: List[str]) -> float:
        """Return how much the roles agree with the majority decision."""
        if not decisions:
            return 0.0
        counts = Counter(decisions)
        return counts.most_common(1)[0][1] / len(decisions)

    @staticmethod
    def _collect_risk_notes(
        role_reviews: List[Dict[str, Any]],
        evidence_slices: Dict[str, List[Dict[str, Any]]],
    ) -> List[str]:
        """Collect and de-duplicate risk notes."""
        notes = []
        for review in role_reviews:
            for note in review.get("risk_notes", []) or []:
                if note and note not in notes:
                    notes.append(str(note))
        if not evidence_slices.get("supporting_evidence"):
            notes.append("no supporting evidence found")
        if evidence_slices.get("opposing_evidence"):
            notes.append("opposing evidence exists")
        return notes

    @staticmethod
    def _final_judgement(decision_counts: Counter, confidence_score: float, oppose_strength: float) -> str:
        """Return final judgement from role votes and evidence risks."""
        if oppose_strength >= 0.4 or decision_counts.get("oppose", 0) >= 2:
            return "not reliable"
        if decision_counts.get("support", 0) >= 3 and confidence_score >= 0.65:
            return "reliable"
        return "needs more evidence"

    @staticmethod
    def _risk_level(confidence_score: float, risk_notes: List[str], oppose_strength: float) -> str:
        """Map confidence and risks into low/medium/high."""
        if confidence_score < 0.45 or oppose_strength >= 0.4 or len(risk_notes) >= 4:
            return "high"
        if confidence_score < 0.7 or risk_notes:
            return "medium"
        return "low"


def calculate_confidence(role_reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convenience function required by the phase 6 interface."""
    return ConfidenceScorer().calculate_confidence(role_reviews)
