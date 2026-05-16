"""Collect and classify evidence for one claim."""

import json
from typing import Any, Dict, List

from ..config import Config
from ..utils.llm_client import LLMClient
from .active_search_service import active_search
from .claim_splitter import PLACEHOLDER_KEYS
from .graph_retriever import graph_retrieve
from .memory_retriever import recall_memory


class EvidenceSlicer:
    """Gather evidence from memory, graph, and optional active search."""

    def __init__(self, config=Config):
        self.config = config

    def slice_evidence_for_claim(self, claim: str, include_active_search: bool = False) -> Dict[str, List[Dict[str, Any]]]:
        """Return supporting, opposing, and neutral evidence slices."""
        claim = (claim or "").strip()
        if not claim:
            raise ValueError("claim is required")
        if self._missing_llm_config():
            raise RuntimeError("LLM_API_KEY or OPENAI_API_KEY is required for evidence slicing")

        evidence = self._collect_evidence(claim, include_active_search=include_active_search)
        if not evidence:
            return {
                "supporting_evidence": [],
                "opposing_evidence": [],
                "neutral_evidence": [],
            }
        return self._classify_with_llm(claim, evidence)

    def _missing_llm_config(self) -> bool:
        """Return true when LLM credentials are missing or placeholders."""
        api_key = (self.config.LLM_API_KEY or self.config.OPENAI_API_KEY or "").strip().lower()
        return api_key in PLACEHOLDER_KEYS

    def _collect_evidence(self, claim: str, include_active_search: bool) -> List[Dict[str, Any]]:
        """Collect evidence from retrieval tools."""
        collected: List[Dict[str, Any]] = []

        for item in recall_memory(claim, top_k=self.config.REVIEW_EVIDENCE_TOP_K):
            collected.append(
                {
                    "type": "memory",
                    "text": item.get("summary") or "",
                    "source": item.get("source") or "",
                    "url": item.get("url") or "",
                    "score": item.get("final_score"),
                }
            )

        for item in graph_retrieve(claim, limit=self.config.REVIEW_EVIDENCE_TOP_K):
            collected.append(
                {
                    "type": "graph",
                    "text": item.get("evidence") or "",
                    "source": item.get("source") or "",
                    "url": item.get("source_url") or "",
                    "relation": item.get("relation"),
                }
            )

        if include_active_search or self.config.REVIEW_USE_ACTIVE_SEARCH:
            for item in active_search(claim)[: self.config.REVIEW_EVIDENCE_TOP_K]:
                collected.append(
                    {
                        "type": "active_search",
                        "text": item.get("raw_text") or "",
                        "source": item.get("source") or "",
                        "url": item.get("url") or "",
                    }
                )

        return [item for item in collected if item.get("text")]

    def _classify_with_llm(self, claim: str, evidence: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Use an LLM to classify evidence stance toward the claim."""
        client = LLMClient()
        response = client.chat_json(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Classify each evidence item against the claim as supporting, opposing, or neutral. "
                        "Return JSON with supporting_evidence, opposing_evidence, neutral_evidence arrays. "
                        "Keep the original evidence fields and add reason."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps({"claim": claim, "evidence": evidence}, ensure_ascii=False),
                },
            ],
            temperature=0.1,
            max_tokens=2500,
        )
        return {
            "supporting_evidence": response.get("supporting_evidence", []),
            "opposing_evidence": response.get("opposing_evidence", []),
            "neutral_evidence": response.get("neutral_evidence", []),
        }


def slice_evidence_for_claim(claim: str) -> Dict[str, List[Dict[str, Any]]]:
    """Convenience function required by the phase 6 interface."""
    return EvidenceSlicer().slice_evidence_for_claim(claim)
