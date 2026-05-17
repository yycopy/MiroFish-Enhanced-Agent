"""Split report text into independently reviewable claims."""

import re
from typing import Dict, List

from ..config import Config
from ..utils.llm_client import LLMClient


PLACEHOLDER_KEYS = {"", "your_api_key_here", "your_openai_api_key_here"}


class ClaimSplitter:
    """Split a draft report into small claims for review."""

    def __init__(self, config=Config):
        self.config = config

    def split_claims(self, report_text: str) -> List[Dict[str, str]]:
        """Return one-verifiable-judgement claims from report text."""
        text = (report_text or "").strip()
        if not text:
            return []

        if not self._missing_llm_config():
            try:
                return self._split_with_llm(text)
            except Exception:
                pass
        return self._split_with_rules(text)

    def _missing_llm_config(self) -> bool:
        """Return true when the LLM key is empty or still a placeholder."""
        api_key = (self.config.LLM_API_KEY or self.config.OPENAI_API_KEY or "").strip().lower()
        return api_key in PLACEHOLDER_KEYS

    def _split_with_llm(self, report_text: str) -> List[Dict[str, str]]:
        """Use an LLM to split text into atomic claims."""
        client = LLMClient()
        response = client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Split the report into atomic, verifiable claims. "
                        "Each claim must contain exactly one judgement. "
                        "Return JSON: {\"claims\": [{\"claim\": \"...\"}]}."
                    ),
                },
                {"role": "user", "content": report_text[:6000]},
            ],
            temperature=0.1,
            max_tokens=1500,
        )
        claims = response.get("claims", [])
        return self._normalize_claims([item.get("claim") if isinstance(item, dict) else item for item in claims])

    def _normalize_claims(self, claims: List[str]) -> List[Dict[str, str]]:
        """Clean, filter, and de-duplicate claims."""
        result = []
        seen = set()
        for claim in claims:
            cleaned = re.sub(r"\s+", " ", str(claim or "")).strip(" -:\uff1a,\uff0c.")
            if len(cleaned) < self.config.REVIEW_CLAIM_MIN_LENGTH:
                continue
            if cleaned in seen:
                continue
            seen.add(cleaned)
            result.append({"claim": cleaned})
            if len(result) >= self.config.REVIEW_MAX_CLAIMS:
                break
        return result

    def _split_with_rules(self, report_text: str) -> List[Dict[str, str]]:
        """Split text into claims with deterministic sentence boundaries."""
        text = re.sub(r"[#>*`_\[\]()]", " ", report_text)
        candidates = re.split(r"(?<=[.!?\u3002\uff01\uff1f])\s+|\n+", text)
        return self._normalize_claims(candidates)


def split_claims(report_text: str) -> List[Dict[str, str]]:
    """Convenience function required by the phase 6 interface."""
    return ClaimSplitter().split_claims(report_text)
