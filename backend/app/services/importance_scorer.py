"""Rule-based importance scoring for active ingestion documents."""

from typing import Dict


class ImportanceScorer:
    """Calculate a 0..1 importance score from transparent rules."""

    AUTHORITY_HINTS = {
        "gov": 0.25,
        "government": 0.25,
        "official": 0.25,
        "regulator": 0.2,
        "central bank": 0.2,
        "news": 0.15,
        "media": 0.12,
        "company": 0.1,
        "research": 0.1,
        "social": 0.05,
    }
    EVENT_HINTS = [
        "发布",
        "宣布",
        "回应",
        "调整",
        "上涨",
        "下跌",
        "讨论",
        "执行",
        "评估",
        "冲击",
        "release",
        "announce",
        "respond",
        "change",
        "increase",
        "decrease",
    ]

    def calculate_importance(self, doc: Dict, summary_result: Dict) -> float:
        """Return a bounded importance score for one document."""
        score = 0.1
        source = (doc.get("source") or "").lower()

        for hint, value in self.AUTHORITY_HINTS.items():
            if hint.lower() in source:
                score += value
                break

        if summary_result.get("entities"):
            score += 0.2
        if summary_result.get("events") or self._contains_event_action(doc):
            score += 0.2
        if summary_result.get("evidence"):
            score += 0.2

        source_count = doc.get("source_count") or 1
        if source_count and int(source_count) > 1:
            score += min(0.2, 0.05 * int(source_count))

        return max(0.0, min(1.0, round(score, 4)))

    def _contains_event_action(self, doc: Dict) -> bool:
        """Check whether the document text contains event-like verbs."""
        text = f"{doc.get('title') or ''} {doc.get('clean_text') or ''}".lower()
        return any(hint.lower() in text for hint in self.EVENT_HINTS)


def calculate_importance(doc: Dict, summary_result: Dict) -> float:
    """Convenience function used by Celery tasks."""
    return ImportanceScorer().calculate_importance(doc, summary_result)
