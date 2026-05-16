"""Evidence trace builder for traceable prediction reports."""

from typing import Any, Dict, List


class EvidenceTraceBuilder:
    """Normalize heterogeneous tool outputs into traceable evidence rows."""

    def build(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build evidence trace rows from memory, graph, search, and interviews."""
        rows: List[Dict[str, Any]] = []
        question = context.get("question") or ""

        self._add_memory(rows, context.get("memory_used") or [], question)
        self._add_graph(rows, context.get("graph_relations_used") or [], question)
        self._add_search(rows, context.get("active_search_used") or [], question)
        self._add_interviews(rows, context.get("agent_interviews") or [], question)

        for index, row in enumerate(rows, 1):
            row["evidence_id"] = f"ev_{index:03d}"
        return rows

    def _add_memory(self, rows: List[Dict[str, Any]], items: List[Dict[str, Any]], question: str) -> None:
        """Add recalled long-term memories."""
        for item in items:
            text = item.get("summary") or item.get("clean_text") or item.get("title") or ""
            if not text:
                continue
            rows.append(
                self._row(
                    evidence_text=text,
                    source_type="memory",
                    source=item.get("source") or "mysql_chroma_memory",
                    url=item.get("url") or "",
                    publish_time=item.get("publish_time") or "",
                    related_claim=question,
                    used_in_section="long_term_memory",
                    metadata={
                        "mysql_id": item.get("id"),
                        "importance_score": item.get("importance_score"),
                        "final_score": item.get("final_score"),
                    },
                )
            )

    def _add_graph(self, rows: List[Dict[str, Any]], items: List[Dict[str, Any]], question: str) -> None:
        """Add retrieved graph relations."""
        for item in items:
            text = item.get("evidence") or self._graph_relation_text(item)
            if not text:
                continue
            rows.append(
                self._row(
                    evidence_text=text,
                    source_type="graph",
                    source=item.get("source") or "zep_graph",
                    url=item.get("source_url") or "",
                    publish_time=item.get("publish_time") or "",
                    related_claim=question,
                    used_in_section="graph_context",
                    metadata={
                        "relation": item.get("relation"),
                        "target": item.get("target"),
                        "mysql_id": item.get("mysql_id"),
                    },
                )
            )

    def _add_search(self, rows: List[Dict[str, Any]], items: List[Dict[str, Any]], question: str) -> None:
        """Add active search documents."""
        for item in items:
            text = item.get("raw_text") or item.get("summary") or item.get("title") or ""
            if not text:
                continue
            rows.append(
                self._row(
                    evidence_text=text,
                    source_type="active_search",
                    source=item.get("source") or "active_search",
                    url=item.get("url") or "",
                    publish_time=item.get("publish_time") or "",
                    related_claim=question,
                    used_in_section="fresh_information",
                    metadata={"title": item.get("title")},
                )
            )

    def _add_interviews(self, rows: List[Dict[str, Any]], items: List[Dict[str, Any]], question: str) -> None:
        """Add agent interviews as opinion evidence, not facts."""
        for item in items:
            text = item.get("response") or item.get("summary") or item.get("action_summary") or ""
            if not text:
                continue
            rows.append(
                self._row(
                    evidence_text=text,
                    source_type="agent_interview",
                    source=item.get("agent_name") or item.get("agent_id") or "simulation_agent",
                    url="",
                    publish_time=item.get("timestamp") or "",
                    related_claim=question,
                    used_in_section="agent_opinions",
                    metadata={
                        "platform": item.get("platform"),
                        "source": item.get("source"),
                    },
                )
            )

    @staticmethod
    def _row(
        *,
        evidence_text: str,
        source_type: str,
        source: Any,
        url: str,
        publish_time: str,
        related_claim: str,
        used_in_section: str,
        metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        """Create one normalized trace row."""
        return {
            "evidence_id": "",
            "evidence_text": EvidenceTraceBuilder._trim(evidence_text),
            "source_type": source_type,
            "source": str(source or ""),
            "url": url or "",
            "publish_time": publish_time or "",
            "related_claim": related_claim or "",
            "used_in_section": used_in_section,
            "metadata": metadata or {},
        }

    @staticmethod
    def _graph_relation_text(item: Dict[str, Any]) -> str:
        """Render graph relation fields into readable evidence text."""
        source = item.get("source") or ""
        relation = item.get("relation") or "related_to"
        target = item.get("target") or ""
        return " ".join(part for part in [source, relation, target] if part)

    @staticmethod
    def _trim(text: Any, limit: int = 1000) -> str:
        """Trim long evidence text without hiding its provenance fields."""
        value = " ".join(str(text or "").split())
        if len(value) <= limit:
            return value
        return value[: limit - 3] + "..."


def build_evidence_trace(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Convenience function for the traceable report tool layer."""
    return EvidenceTraceBuilder().build(context)
