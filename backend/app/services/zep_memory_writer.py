"""Write structured long-term memory into Zep GraphRAG.

This writer keeps the original Zep graph flow intact. It converts the enhanced
summary fields from phase 4 into a JSON/text episode that Zep can extract into
entities and relationships using the enhanced schema.
"""

import json
import re
from typing import Any, Dict, List, Optional

from zep_cloud.client import Zep

from ..config import Config
from ..utils.logger import get_logger
from .zep_schema_service import ENTITY_TYPES, RELATION_TYPES, ZepSchemaService


logger = get_logger("mirofish.zep_memory_writer")

PLACEHOLDER_KEYS = {"", "your_zep_api_key_here", "your_api_key_here"}


class ZepGraphMemoryUnavailable(RuntimeError):
    """Raised when enhanced Zep graph memory cannot be used."""


class ZepMemoryWriter:
    """Write memory_item-derived graph context into Zep."""

    def __init__(self, graph_id: Optional[str] = None, api_key: Optional[str] = None):
        self.graph_id = graph_id or Config.ZEP_ENHANCED_GRAPH_ID
        self.api_key = (api_key or Config.ZEP_API_KEY or "").strip()
        if self.api_key.lower() in PLACEHOLDER_KEYS:
            raise ZepGraphMemoryUnavailable("ZEP_API_KEY is not configured")
        if not self.graph_id:
            raise ZepGraphMemoryUnavailable("ZEP_ENHANCED_GRAPH_ID is not configured")

        self.client = Zep(api_key=self.api_key)
        self.schema_service = ZepSchemaService()

    def write_graph_memory(self, memory_item: Dict[str, Any]) -> Dict[str, Any]:
        """Write one structured memory item into the enhanced Zep graph."""
        self._ensure_graph_and_schema()
        episode_payload = self._build_episode_payload(memory_item)
        episode_text = self._build_episode_text(episode_payload)

        created_at = self._normalize_created_at(episode_payload.get("publish_time") or None)

        try:
            episode = self.client.graph.add(
                graph_id=self.graph_id,
                type="json",
                data=json.dumps(episode_payload, ensure_ascii=False),
                created_at=created_at,
                source_description=f"mirofish enhanced graph memory mysql_id={episode_payload.get('mysql_id')}",
            )
        except Exception as exc:
            # Some Zep deployments extract text more reliably than JSON. Keep a
            # text fallback while preserving the same metadata in the content.
            logger.warning("zep json graph add failed, retrying as text: %s", exc)
            try:
                episode = self.client.graph.add(
                    graph_id=self.graph_id,
                    type="text",
                    data=episode_text,
                    created_at=created_at,
                    source_description=f"mirofish enhanced graph memory mysql_id={episode_payload.get('mysql_id')}",
                )
            except Exception as text_exc:
                raise ZepGraphMemoryUnavailable(str(text_exc)) from text_exc

        triple_count = self._write_fact_triples(episode_payload, created_at)
        return {
            "graph_id": self.graph_id,
            "episode_uuid": getattr(episode, "uuid_", None) or getattr(episode, "uuid", None),
            "entity_count": len(episode_payload["entities"]),
            "relation_count": len(episode_payload["relations"]),
            "triple_count": triple_count,
            "schema": {
                "entities": ENTITY_TYPES,
                "relations": RELATION_TYPES,
            },
        }

    def _ensure_graph_and_schema(self) -> None:
        """Create the enhanced graph if needed and apply schema best-effort."""
        try:
            self.client.graph.create(
                graph_id=self.graph_id,
                name="MiroFish Enhanced Graph Memory",
                description="Enhanced entity-relation memory for active ingestion.",
            )
        except Exception:
            # Graph may already exist. Zep Cloud returns provider-specific errors,
            # so we keep this best-effort and continue to ontology setup.
            pass

        try:
            self.schema_service.apply_to_graph(self.client, self.graph_id)
        except Exception as exc:
            logger.warning("failed to apply enhanced zep schema, continuing with episode write: %s", exc)

    def _build_episode_payload(self, memory_item: Dict[str, Any]) -> Dict[str, Any]:
        """Build a structured graph episode from a MySQL memory item or task payload."""
        summary = memory_item.get("summary") or ""
        entities = self._normalize_entities(memory_item.get("entities"), summary)
        events = self._normalize_named_values(memory_item.get("events"), "event", summary)
        opinions = self._normalize_named_values(memory_item.get("opinions"), "opinion", summary)
        evidence = self._normalize_evidence(memory_item.get("evidence"), memory_item)
        stances = self._normalize_named_values(memory_item.get("stances") or memory_item.get("stance"), "stance", "")

        source_url = memory_item.get("source_url") or memory_item.get("url") or ""
        publish_time = memory_item.get("publish_time") or ""
        mysql_id = memory_item.get("mysql_id") or memory_item.get("id")

        graph_entities = []
        graph_entities.extend(entities)
        graph_entities.extend(events)
        graph_entities.extend(opinions)
        graph_entities.extend(evidence)
        graph_entities.extend(stances)

        relations = self._build_relations(
            entities=entities,
            events=events,
            opinions=opinions,
            evidence=evidence,
            stances=stances,
            source_url=source_url,
            publish_time=publish_time,
            mysql_id=mysql_id,
        )

        return {
            "schema": "mirofish_enhanced_graph_memory_v1",
            "mysql_id": mysql_id,
            "source": memory_item.get("source") or "",
            "source_url": source_url,
            "publish_time": publish_time,
            "summary": summary,
            "uncertainty": memory_item.get("uncertainty") or "",
            "entities": graph_entities,
            "relations": relations,
        }

    @staticmethod
    def _normalize_created_at(value: Optional[str]) -> Optional[str]:
        """Return an RFC3339-ish timestamp accepted by the Zep graph API."""
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        if text.endswith("Z") or re.search(r"[+-]\d{2}:\d{2}$", text):
            return text
        if "T" in text:
            return f"{text}Z"
        return text

    def _build_relations(
        self,
        *,
        entities: List[Dict[str, str]],
        events: List[Dict[str, str]],
        opinions: List[Dict[str, str]],
        evidence: List[Dict[str, str]],
        stances: List[Dict[str, str]],
        source_url: str,
        publish_time: str,
        mysql_id: Any,
    ) -> List[Dict[str, Any]]:
        """Create explicit relationship candidates with metadata."""
        relations: List[Dict[str, Any]] = []
        metadata = {
            "source_url": self._truncate(source_url, 240),
            "publish_time": self._truncate(publish_time, 40),
            "mysql_id": self._truncate(mysql_id, 40),
        }

        for source in entities:
            for opinion in opinions:
                relations.append(self._relation(source, "expresses", opinion, metadata))
            for event in events:
                relations.append(self._relation(source, "mentions", event, metadata))
            for stance in stances:
                relation_name = "opposes" if "反对" in stance["name"] or "oppos" in stance["name"].lower() else "supports"
                relations.append(self._relation(source, relation_name, stance, metadata))

        for opinion in opinions:
            for event in events:
                relations.append(self._relation(opinion, "responds_to", event, metadata))
            for item in evidence:
                evidence_metadata = {**metadata, "evidence_text": item.get("text") or item.get("name") or ""}
                relations.append(self._relation(opinion, "based_on", item, evidence_metadata))

        for event in events:
            for item in evidence:
                evidence_metadata = {**metadata, "evidence_text": item.get("text") or item.get("name") or ""}
                relations.append(self._relation(item, "mentions", event, evidence_metadata))

        return relations

    def _write_fact_triples(self, payload: Dict[str, Any], created_at: Optional[str]) -> int:
        """Write explicit Zep fact triples so graph retrieval is immediately usable."""
        written = 0
        for relation in payload.get("relations") or []:
            source = self._truncate(relation.get("source"), 50)
            target = self._truncate(relation.get("target"), 50)
            if not source or not target:
                continue
            if source.casefold() == target.casefold():
                continue

            metadata = relation.get("metadata") or {}
            relation_name = str(relation.get("relation") or "related_to")
            fact_name = relation_name.upper()
            evidence_text = self._truncate(metadata.get("evidence_text"), 70)
            source_url = self._truncate(metadata.get("source_url"), 70)
            publish_time = self._truncate(metadata.get("publish_time"), 30)
            mysql_id = self._truncate(metadata.get("mysql_id"), 20)
            fact = (
                f"{source} {relation_name} {target}; "
                f"source_url={source_url}; "
                f"publish_time={publish_time}; "
                f"mysql_id={mysql_id}; "
                f"evidence_text={evidence_text}"
            )
            fact = self._truncate(fact, 250)

            try:
                self.client.graph.add_fact_triple(
                    graph_id=self.graph_id,
                    fact=fact,
                    fact_name=fact_name,
                    source_node_name=str(source),
                    target_node_name=str(target),
                    source_node_summary=str(relation.get("source_type") or ""),
                    target_node_summary=str(relation.get("target_type") or ""),
                    created_at=created_at,
                )
                written += 1
            except Exception as exc:
                logger.warning("failed to write zep fact triple %s -> %s: %s", source, target, exc)
        return written

    @staticmethod
    def _truncate(value: Any, max_length: int) -> str:
        """Trim values to Zep API field limits while keeping them readable."""
        text = str(value or "").strip()
        if len(text) <= max_length:
            return text
        return text[: max(0, max_length - 1)].rstrip() + "…"

    @staticmethod
    def _relation(source: Dict[str, str], relation: str, target: Dict[str, str], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Build a relationship dictionary with source metadata."""
        return {
            "source": source.get("name"),
            "source_type": source.get("type"),
            "relation": relation,
            "target": target.get("name"),
            "target_type": target.get("type"),
            "metadata": metadata,
        }

    def _normalize_entities(self, value: Any, summary: str) -> List[Dict[str, str]]:
        """Normalize entity values and infer a broad type if needed."""
        entities = []
        for item in self._as_list(value):
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("text") or "").strip()
                entity_type = str(item.get("type") or self._infer_entity_type(name)).strip()
            else:
                name = str(item).strip()
                entity_type = self._infer_entity_type(name)
            if name:
                entities.append({"name": name, "type": entity_type})

        if not entities and summary:
            for name in re.findall(r"[\u4e00-\u9fff]{2,12}|[A-Z][A-Za-z0-9_.-]{2,}", summary)[:5]:
                entities.append({"name": name, "type": self._infer_entity_type(name)})

        return self._dedup_entities(entities)

    def _normalize_named_values(self, value: Any, entity_type: str, fallback: str) -> List[Dict[str, str]]:
        """Normalize strings/dicts into typed graph entities."""
        items = []
        for item in self._as_list(value):
            if isinstance(item, dict):
                name = str(item.get("name") or item.get("text") or item.get("summary") or "").strip()
            else:
                name = str(item).strip()
            if name:
                items.append({"name": name[:180], "type": entity_type})
        if not items and fallback and entity_type in {"opinion", "event"}:
            items.append({"name": fallback[:180], "type": entity_type})
        return self._dedup_entities(items)

    def _normalize_evidence(self, value: Any, memory_item: Dict[str, Any]) -> List[Dict[str, str]]:
        """Normalize evidence slices from summary output or memory_evidence rows."""
        evidence = []
        for item in self._as_list(value):
            if isinstance(item, dict):
                text = str(item.get("evidence_text") or item.get("text") or item.get("claim") or "").strip()
            else:
                text = str(item).strip()
            if text:
                evidence.append({"name": text[:120], "text": text, "type": "evidence"})

        if not evidence and memory_item.get("clean_text"):
            text = str(memory_item.get("clean_text") or "")[:240]
            evidence.append({"name": text[:120], "text": text, "type": "evidence"})

        return self._dedup_entities(evidence)

    @staticmethod
    def _as_list(value: Any) -> List[Any]:
        """Normalize None/scalar/list values into a list."""
        if value is None:
            return []
        if isinstance(value, list):
            return value
        return [value]

    @staticmethod
    def _dedup_entities(values: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Remove duplicate names while preserving order."""
        seen = set()
        result = []
        for item in values:
            key = (item.get("name"), item.get("type"))
            if key in seen:
                continue
            seen.add(key)
            result.append(item)
        return result

    @staticmethod
    def _infer_entity_type(name: str) -> str:
        """Infer person vs organization with transparent lightweight rules."""
        organization_hints = ["公司", "集团", "政府", "部门", "机构", "委员会", "学校", "银行", "媒体", "平台"]
        if any(hint in name for hint in organization_hints):
            return "organization"
        return "person"

    def _build_episode_text(self, payload: Dict[str, Any]) -> str:
        """Build a readable fallback text episode."""
        lines = [
            "MiroFish enhanced graph memory",
            f"mysql_id: {payload.get('mysql_id')}",
            f"source_url: {payload.get('source_url')}",
            f"publish_time: {payload.get('publish_time')}",
            f"summary: {payload.get('summary')}",
            f"uncertainty: {payload.get('uncertainty')}",
            "",
            "entities:",
        ]
        for entity in payload.get("entities") or []:
            lines.append(f"- {entity.get('name')} ({entity.get('type')})")
        lines.append("")
        lines.append("relations:")
        for relation in payload.get("relations") or []:
            meta = relation.get("metadata") or {}
            lines.append(
                f"- {relation.get('source')} [{relation.get('relation')}] {relation.get('target')}; "
                f"source_url={meta.get('source_url')}; publish_time={meta.get('publish_time')}; "
                f"mysql_id={meta.get('mysql_id')}; evidence_text={meta.get('evidence_text', '')}"
            )
        return "\n".join(lines)


def write_graph_memory(memory_item: Dict[str, Any]) -> Dict[str, Any]:
    """Convenience function required by the phase 5 interface."""
    return ZepMemoryWriter().write_graph_memory(memory_item)
