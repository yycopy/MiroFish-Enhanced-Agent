"""Independent multi-role claim review agents."""

import json
from typing import Any, Dict, List

from ..config import Config
from ..utils.llm_client import LLMClient
from .claim_splitter import PLACEHOLDER_KEYS


REVIEW_ROLES = ["fact_checker", "supporter", "opponent", "risk_reviewer", "evidence_organizer"]

ROLE_PROMPTS = {
    "fact_checker": "Check whether the claim is factually supported by evidence. Be strict.",
    "supporter": "Argue for the claim using only evidence that supports it.",
    "opponent": "Argue against the claim and look for counter-evidence.",
    "risk_reviewer": "Find hallucination, overclaiming, missing evidence, and uncertainty risks.",
    "evidence_organizer": "Organize evidence quality and identify the clearest traceable evidence.",
}


class ReviewAgent:
    """Run independent LLM reviews for each role."""

    def __init__(self, config=Config):
        self.config = config

    def review_claim(self, claim: str, evidence_slices: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Review a claim with all configured roles independently."""
        if self._missing_llm_config():
            raise RuntimeError("LLM_API_KEY or OPENAI_API_KEY is required for multi-agent review")
        return [self._review_with_llm(role, claim, evidence_slices) for role in REVIEW_ROLES]

    def review_claim_batched(self, claim: str, evidence_slices: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
        """Review a claim with all roles in one LLM call for report latency.

        This fast path is used by the traceable report endpoint so a frontend
        demo does not wait on many serial LLM calls. The prompt still asks each
        role to judge from the claim and evidence only, and the standalone
        review API continues to use fully separate role calls.
        """
        if self._missing_llm_config():
            raise RuntimeError("LLM_API_KEY or OPENAI_API_KEY is required for multi-agent review")

        client = LLMClient()
        response = client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Review the claim from five independent roles. For each role, use only the claim and evidence, "
                        "do not reference other roles, and return one judgement. "
                        "Return JSON with key role_reviews. Each item must contain role, support_decision, reason, "
                        "key_evidence, risk_notes, confidence. support_decision must be support, oppose, or uncertain."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "roles": {role: ROLE_PROMPTS[role] for role in REVIEW_ROLES},
                            "claim": claim,
                            "evidence_slices": evidence_slices,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            temperature=0.1,
            max_tokens=2500,
        )
        raw_reviews = response.get("role_reviews") or response.get("reviews") or []
        by_role = {}
        for item in raw_reviews if isinstance(raw_reviews, list) else []:
            role = str(item.get("role") or "").strip()
            if role in REVIEW_ROLES:
                by_role[role] = self._normalize_review(role, item)

        return [
            by_role.get(
                role,
                {
                    "role": role,
                    "support_decision": "uncertain",
                    "reason": "the batched reviewer did not return this role",
                    "key_evidence": [],
                    "risk_notes": ["missing role output"],
                    "confidence": 0.3,
                },
            )
            for role in REVIEW_ROLES
        ]

    def fallback_review_claim(
        self,
        claim: str,
        evidence_slices: Dict[str, List[Dict[str, Any]]],
        reason: str,
    ) -> List[Dict[str, Any]]:
        """Build conservative role reviews when the LLM provider is unavailable."""
        supporting = evidence_slices.get("supporting_evidence", []) or []
        opposing = evidence_slices.get("opposing_evidence", []) or []
        neutral = evidence_slices.get("neutral_evidence", []) or []
        all_evidence = supporting + opposing + neutral

        if opposing:
            base_decision = "oppose"
        elif supporting:
            base_decision = "support"
        else:
            base_decision = "uncertain"

        confidence = 0.35 + min(0.25, len(supporting) * 0.08) - min(0.2, len(opposing) * 0.08)
        confidence = max(0.15, min(0.65, confidence))

        key_evidence = [
            str(item.get("text") or item.get("evidence_text") or item.get("summary") or item)[:180]
            for item in all_evidence[:5]
        ]

        claim_short = (claim or "")[:60]
        ev_count = len(all_evidence)
        sup_count = len(supporting)
        opp_count = len(opposing)

        # Role-specific review reasons
        role_reasons = {
            "fact_checker": (
                f"基于现有 {ev_count} 条证据进行基础事实核查。"
                f"其中 {sup_count} 条支持，{opp_count} 条反对。"
                + ("证据较充分。" if sup_count >= 2 else "证据数量不足，建议谨慎对待。")
            ),
            "supporter": (
                f"从支持角度分析，找到 {sup_count} 条支持性证据。"
                + (f"主要支持依据来自 {len(key_evidence)} 条关键证据。" if sup_count > 0
                   else "暂未找到直接支持该论断的证据。")
            ),
            "opponent": (
                f"从反对角度审视，发现 {opp_count} 条反对证据。"
                + ("存在明确的反面论据，需要进一步验证。" if opp_count > 0
                   else "未发现直接反驳证据，但缺乏充分验证。")
            ),
            "risk_reviewer": (
                f"风险评估：当前证据链包含 {ev_count} 条证据。"
                + ("反对证据的存在增加了预测风险。" if opp_count > 0
                   else "证据来源类型覆盖" + ("较全面。" if ev_count >= 3 else "有限，存在信息不完整的风险。"))
            ),
            "evidence_organizer": (
                f"证据组织评估：共收集 {ev_count} 条证据，"
                f"其中支持类 {sup_count} 条、反对类 {opp_count} 条、中立类 {len(neutral)} 条。"
                + ("证据结构较完整。" if ev_count >= 3 else "证据链覆盖不足，建议补充更多来源。")
            ),
        }

        risk_notes = [
            f"LLM评审不可用，已启用规则回退: {reason[:100]}",
            "此为基础分析，非完整LLM评审结果",
        ]
        if not supporting:
            risk_notes.append("未找到支持性证据")
        if opposing:
            risk_notes.append(f"存在 {opp_count} 条反对证据")

        reviews = []
        for role in REVIEW_ROLES:
            decision = base_decision
            role_confidence = confidence
            if role == "risk_reviewer":
                decision = "uncertain"
                role_confidence = max(0.15, confidence - 0.1)
            if role == "opponent" and not opposing:
                decision = "uncertain"
            if role == "supporter" and not supporting:
                decision = "uncertain"
                role_confidence = max(0.15, confidence - 0.15)
            reviews.append(
                {
                    "role": role,
                    "support_decision": decision,
                    "reason": role_reasons.get(role, f"规则回退评审: {claim_short}"),
                    "key_evidence": key_evidence,
                    "risk_notes": risk_notes,
                    "confidence": round(role_confidence, 4),
                }
            )
        return reviews

    def _missing_llm_config(self) -> bool:
        """Return true when LLM credentials are missing or placeholders."""
        api_key = (self.config.LLM_API_KEY or self.config.OPENAI_API_KEY or "").strip().lower()
        return api_key in PLACEHOLDER_KEYS

    def _review_with_llm(self, role: str, claim: str, evidence_slices: Dict[str, Any]) -> Dict[str, Any]:
        """Run one low-temperature role review without other role outputs."""
        client = LLMClient()
        response = client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"You are the {role}. {ROLE_PROMPTS[role]} "
                        "Return JSON: role, support_decision, reason, key_evidence, risk_notes, confidence. "
                        "support_decision must be support, oppose, or uncertain. confidence is 0..1."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"claim": claim, "evidence_slices": evidence_slices}, ensure_ascii=False),
                },
            ],
            temperature=0.1,
            max_tokens=1200,
        )
        return self._normalize_review(role, response)

    def _normalize_review(self, role: str, review: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize role output to the required schema."""
        decision = str(review.get("support_decision") or "uncertain").lower()
        if decision not in {"support", "oppose", "uncertain"}:
            decision = "uncertain"
        return {
            "role": role,
            "support_decision": decision,
            "reason": str(review.get("reason") or ""),
            "key_evidence": self._list_of_strings(review.get("key_evidence")),
            "risk_notes": self._list_of_strings(review.get("risk_notes")),
            "confidence": self._clamp(review.get("confidence"), default=0.5),
        }

    @staticmethod
    def _list_of_strings(value: Any) -> List[str]:
        """Normalize scalar/list values into string list."""
        if value is None:
            return []
        if isinstance(value, list):
            return [str(item) for item in value if str(item)]
        return [str(value)]

    @staticmethod
    def _clamp(value: Any, default: float = 0.5) -> float:
        """Clamp confidence to 0..1."""
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = default
        return max(0.0, min(1.0, number))


def review_claim(claim: str, evidence_slices: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convenience function for multi-role review."""
    return ReviewAgent().review_claim(claim, evidence_slices)
