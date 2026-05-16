"""Enhanced graph retrieval for Agent context."""

import re
from typing import Any, Dict, List, Optional

from ..config import Config
from .zep_memory_writer import PLACEHOLDER_KEYS, ZepGraphMemoryUnavailable
from .zep_tools import ZepToolsService


class GraphRetriever:
    """Retrieve enhanced entity-relation memory from Zep."""

    def __init__(self, graph_id: Optional[str] = None, api_key: Optional[str] = None):
        self.graph_id = graph_id or Config.ZEP_ENHANCED_GRAPH_ID
        self.api_key = (api_key or Config.ZEP_API_KEY or "").strip()
        if self.api_key.lower() in PLACEHOLDER_KEYS:
            raise ZepGraphMemoryUnavailable("ZEP_API_KEY is not configured")
        self.tools = ZepToolsService(api_key=self.api_key)

    def graph_retrieve(self, question: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search Zep and return structured graph context."""
        question = (question or "").strip()
        if not question:
            raise ValueError("question is required")

        queries = [question] + self.extract_key_entities(question)[:3]
        rows: List[Dict[str, Any]] = []
        seen = set()
        node_map = self._safe_node_map()

        for query in queries:
            result = self.tools.search_graph(
                graph_id=self.graph_id,
                query=query,
                limit=limit,
                scope="edges",
            )
            for edge in result.edges:
                fact = edge.get("fact") or ""
                key = edge.get("uuid") or fact
                if key in seen:
                    continue
                seen.add(key)
                source = (
                    edge.get("source_node_name")
                    or node_map.get(edge.get("source_node_uuid"))
                    or self._extract_source_from_fact(fact)
                )
                target = (
                    edge.get("target_node_name")
                    or node_map.get(edge.get("target_node_uuid"))
                    or self._extract_target_from_fact(fact)
                )
                rows.append(
                    {
                        "source": source,
                        "relation": self._normalize_relation(edge.get("name") or fact),
                        "target": target,
                        "evidence": fact,
                        "source_url": self._extract_metadata(fact, "source_url"),
                        "publish_time": self._extract_metadata(fact, "publish_time"),
                        "mysql_id": self._extract_metadata(fact, "mysql_id"),
                    }
                )
                if len(rows) >= limit:
                    return rows

        return rows

    def extract_key_entities(self, question: str) -> List[str]:
        """Extract lightweight key entities from a question."""
        patterns = [
            r"[\u4e00-\u9fff]{1,8}[A-Za-z0-9][A-Za-z0-9_.-]*",
            r"[A-Za-z][A-Za-z0-9_.-]{2,}",
            r"[\u4e00-\u9fff]{2,8}",
        ]
        candidates = []
        for pattern in patterns:
            candidates.extend(re.findall(pattern, question))
        stopwords = {"后续", "未来", "怎么", "发展", "什么", "影响", "方案"}
        result = []
        for item in candidates:
            if item in stopwords or item.lower() in stopwords:
                continue
            if re.fullmatch(r"[\u4e00-\u9fff]+", item) and any(word in item for word in stopwords):
                continue
            if re.fullmatch(r"[\u4e00-\u9fff]+", item) and any(item in existing for existing in result):
                continue
            if item not in result:
                result.append(item)
        return result

    def _safe_node_map(self) -> Dict[str, str]:
        """Fetch node names best-effort for clearer edge output."""
        try:
            return {node.uuid: node.name for node in self.tools.get_all_nodes(self.graph_id)}
        except Exception:
            return {}

    @staticmethod
    def _normalize_relation(value: str) -> str:
        """Normalize a Zep edge name or fact text to a known relation label."""
        text = (value or "").lower()
        for relation in [
            "supports",
            "opposes",
            "publishes",
            "mentions",
            "causes",
            "influences",
            "based_on",
            "expresses",
            "responds_to",
            "changes_stance",
        ]:
            if relation in text:
                return relation
        return value or "related_to"

    @staticmethod
    def _extract_metadata(text: str, key: str) -> str:
        """Extract metadata embedded in enhanced episode facts."""
        match = re.search(
            rf"['\"]?{re.escape(key)}['\"]?\s*[=:]\s*['\"]?([^;\"'\n,}}]+)",
            text or "",
        )
        return match.group(1).strip() if match else ""

    @staticmethod
    def _extract_source_from_fact(text: str) -> str:
        """Best-effort source extraction from a fact sentence."""
        match = re.match(r"(.+?)\s+(supports|opposes|publishes|mentions|causes|influences|based_on|expresses|responds_to|changes_stance|\[)", text or "", re.I)
        return match.group(1).strip(" -:[]") if match else ""

    @staticmethod
    def _extract_target_from_fact(text: str) -> str:
        """Best-effort target extraction from a fact sentence."""
        match = re.search(r"(?:supports|opposes|publishes|mentions|causes|influences|based_on|expresses|responds_to|changes_stance|\])\s+(.+?)(?:;|$)", text or "", re.I)
        return match.group(1).strip(" -:[]") if match else ""


def graph_retrieve(question: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Convenience function required by the phase 5 interface."""
    return GraphRetriever().graph_retrieve(question, limit=limit)
