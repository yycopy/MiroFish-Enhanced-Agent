"""API endpoints for multi-agent credibility review."""

from flask import jsonify, request

from ..db import DatabaseUnavailableError, create_all_tables
from ..repositories.review_repository import ReviewRepository
from ..services.claim_splitter import ClaimSplitter
from ..services.confidence_scorer import ConfidenceScorer
from ..services.evidence_slicer import EvidenceSlicer
from ..services.review_agent import ReviewAgent
from . import review_bp


claim_splitter = ClaimSplitter()
evidence_slicer = EvidenceSlicer()
review_agent = ReviewAgent()
confidence_scorer = ConfidenceScorer()
review_repository = ReviewRepository()


@review_bp.route("/claims", methods=["POST"])
def split_report_claims():
    """Split a draft report into reviewable claims."""
    payload = request.get_json(silent=True) or {}
    report_text = payload.get("report_text") or ""
    claims = claim_splitter.split_claims(report_text)
    return jsonify({"success": True, "claims": claims, "count": len(claims)})


@review_bp.route("/evaluate", methods=["POST"])
def evaluate_claim():
    """Evaluate one claim with evidence slicing and multi-role review."""
    payload = request.get_json(silent=True) or {}
    claim = (payload.get("claim") or "").strip()
    if not claim:
        return jsonify({"success": False, "error": "claim is required"}), 400

    result = _evaluate_one_claim(
        claim,
        include_active_search=bool(payload.get("include_active_search", False)),
        persist=bool(payload.get("persist", True)),
    )
    return jsonify({"success": True, **result})


@review_bp.route("/report", methods=["POST"])
def evaluate_report():
    """Evaluate all claims in a draft report."""
    payload = request.get_json(silent=True) or {}
    report_text = (payload.get("report_text") or "").strip()
    if not report_text:
        return jsonify({"success": False, "error": "report_text is required"}), 400

    claims = claim_splitter.split_claims(report_text)
    results = [
        _evaluate_one_claim(
            item["claim"],
            include_active_search=bool(payload.get("include_active_search", False)),
            persist=bool(payload.get("persist", True)),
        )
        for item in claims
    ]
    return jsonify({"success": True, "claims": claims, "results": results, "count": len(results)})


def _evaluate_one_claim(claim: str, *, include_active_search: bool, persist: bool) -> dict:
    """Run the full review workflow for one claim."""
    try:
        evidence_slices = evidence_slicer.slice_evidence_for_claim(
            claim,
            include_active_search=include_active_search,
        )
    except Exception as exc:
        evidence_slices = {
            "supporting_evidence": [],
            "opposing_evidence": [],
            "neutral_evidence": [],
        }
        role_reviews = review_agent.fallback_review_claim(
            claim,
            evidence_slices,
            f"evidence slicing failed: {exc}",
        )
    else:
        try:
            role_reviews = review_agent.review_claim(claim, evidence_slices)
        except Exception as exc:
            role_reviews = review_agent.fallback_review_claim(claim, evidence_slices, str(exc))
    confidence_result = confidence_scorer.calculate_confidence(role_reviews, evidence_slices)
    persistence = _persist_review_best_effort(
        claim=claim,
        evidence_slices=evidence_slices,
        role_reviews=role_reviews,
        confidence_result=confidence_result,
        enabled=persist,
    )

    return {
        "claim": claim,
        "evidence": evidence_slices,
        "role_reviews": role_reviews,
        **confidence_result,
        "persistence": persistence,
    }


def _persist_review_best_effort(
    *,
    claim: str,
    evidence_slices: dict,
    role_reviews: list,
    confidence_result: dict,
    enabled: bool,
) -> dict:
    """Persist review if MySQL is available, otherwise return a clear marker."""
    if not enabled:
        return {"persisted": False, "reason": "disabled by request"}
    try:
        create_all_tables()
        row = review_repository.create_review(
            claim=claim,
            evidence_slices=evidence_slices,
            role_reviews=role_reviews,
            confidence_result=confidence_result,
        )
        return {"persisted": True, "review_id": row.get("id")}
    except DatabaseUnavailableError as exc:
        return {"persisted": False, "reason": str(exc)}
    except Exception as exc:
        return {"persisted": False, "reason": str(exc)}
