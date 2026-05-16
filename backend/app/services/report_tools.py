"""Tool wrappers for the traceable ReportAgent."""

import json
import os
from typing import Any, Dict, List, Optional

from ..config import Config
from .active_search_service import active_search
from .claim_splitter import ClaimSplitter
from .confidence_scorer import ConfidenceScorer
from .evidence_slicer import EvidenceSlicer
from .evidence_trace import build_evidence_trace
from .graph_retriever import GraphRetriever
from .memory_retriever import recall_memory
from .review_agent import ReviewAgent
from .simulation_manager import SimulationManager
from .simulation_runner import SimulationRunner


class ReportToolset:
    """Best-effort tools used by the traceable report agent."""

    def __init__(self, config=Config):
        self.config = config

    def memory_recall_tool(self, question: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """Recall long-term memories from Chroma and MySQL."""
        try:
            items = recall_memory(question, top_k=top_k or self.config.TRACEABLE_REPORT_MEMORY_TOP_K)
            return {"success": True, "items": items, "error": None}
        except Exception as exc:
            return {"success": False, "items": [], "error": str(exc)}

    def graph_retrieve_tool(
        self,
        question: str,
        graph_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Retrieve entity-relation context from enhanced Zep GraphRAG."""
        try:
            retriever = GraphRetriever(graph_id=graph_id) if graph_id else GraphRetriever()
            items = retriever.graph_retrieve(question, limit=limit or self.config.TRACEABLE_REPORT_GRAPH_LIMIT)
            return {"success": True, "items": items, "error": None}
        except Exception as exc:
            return {"success": False, "items": [], "error": str(exc)}

    def active_search_tool(self, question: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Run active search through the configured provider."""
        try:
            items = active_search(question)
            max_items = limit or self.config.TRACEABLE_REPORT_MAX_SEARCH_RESULTS
            return {"success": True, "items": items[:max_items], "error": None}
        except Exception as exc:
            return {"success": False, "items": [], "error": str(exc)}

    def interview_agents_tool(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Read live agent interviews, history, or saved simulation actions."""
        simulation_id = self._resolve_simulation_id(context)
        if not simulation_id:
            return {
                "success": True,
                "items": [],
                "source": "none",
                "skipped": True,
                "warnings": ["no simulation_id or project simulation was found"],
                "error": None,
            }

        errors: List[str] = []

        live = self._try_live_interview(simulation_id, question)
        if live["items"]:
            live["simulation_id"] = simulation_id
            return live
        if live.get("error"):
            errors.append(live["error"])

        history = self._try_interview_history(simulation_id)
        if history["items"]:
            history["simulation_id"] = simulation_id
            history["warnings"] = errors
            return history
        if history.get("error"):
            errors.append(history["error"])

        actions = self._try_recent_actions(simulation_id)
        if actions["items"]:
            actions["simulation_id"] = simulation_id
            actions["warnings"] = errors
            return actions
        if actions.get("error"):
            errors.append(actions["error"])

        return {
            "success": True,
            "items": [],
            "source": "simulation",
            "simulation_id": simulation_id,
            "skipped": True,
            "warnings": errors,
            "error": None,
        }

    def confidence_review_tool(self, report_text: str) -> Dict[str, Any]:
        """Run phase 6 multi-agent review without forcing persistence."""
        try:
            splitter = ClaimSplitter(config=self.config)
            slicer = EvidenceSlicer(config=self.config)
            reviewer = ReviewAgent(config=self.config)
            scorer = ConfidenceScorer()

            claims = splitter.split_claims(report_text)
            max_claims = max(1, int(getattr(self.config, "TRACEABLE_REPORT_REVIEW_MAX_CLAIMS", 2)))
            claims_to_review = claims[:max_claims]
            results = []
            for item in claims_to_review:
                claim = item["claim"]
                try:
                    evidence = slicer.slice_evidence_for_claim(claim)
                except Exception as exc:
                    evidence = {
                        "supporting_evidence": [],
                        "opposing_evidence": [],
                        "neutral_evidence": [],
                    }
                    role_reviews = reviewer.fallback_review_claim(claim, evidence, f"evidence slicing failed: {exc}")
                else:
                    try:
                        if getattr(self.config, "TRACEABLE_REPORT_FAST_REVIEW", True):
                            role_reviews = reviewer.review_claim_batched(claim, evidence)
                        else:
                            role_reviews = reviewer.review_claim(claim, evidence)
                    except Exception as exc:
                        role_reviews = reviewer.fallback_review_claim(claim, evidence, str(exc))
                confidence = scorer.calculate_confidence(role_reviews, evidence)
                results.append(
                    {
                        "claim": claim,
                        "evidence": evidence,
                        "role_reviews": role_reviews,
                        **confidence,
                    }
                )

            return {
                "success": True,
                "claims": claims,
                "claims_reviewed": claims_to_review,
                "results": results,
                "summary": self._review_summary(results),
                "error": None,
            }
        except Exception as exc:
            return {"success": False, "claims": [], "results": [], "summary": "", "error": str(exc)}

    def evidence_trace_tool(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build normalized evidence trace rows."""
        return build_evidence_trace(context)

    def _resolve_simulation_id(self, context: Dict[str, Any]) -> Optional[str]:
        """Resolve simulation id from explicit input or project id."""
        simulation_id = context.get("simulation_id")
        if simulation_id:
            return simulation_id

        project_id = context.get("project_id")
        if not project_id:
            return None

        try:
            manager = SimulationManager()
            simulations = manager.list_simulations(project_id=project_id)
        except Exception:
            return None

        if not simulations:
            return None
        simulations.sort(key=lambda item: item.updated_at or item.created_at, reverse=True)
        return simulations[0].simulation_id

    def _try_live_interview(self, simulation_id: str, question: str) -> Dict[str, Any]:
        """Call a live OASIS interview when the simulation environment is alive."""
        try:
            if not SimulationRunner.check_env_alive(simulation_id):
                return {"success": False, "items": [], "error": "simulation environment is not alive"}

            result = SimulationRunner.interview_all_agents(
                simulation_id=simulation_id,
                prompt=question,
                platform=None,
                timeout=self.config.TRACEABLE_REPORT_INTERVIEW_TIMEOUT_SECONDS,
            )
            items = self._normalize_live_interviews(result)
            return {"success": bool(items), "items": items, "source": "live_oasis", "error": None}
        except Exception as exc:
            return {"success": False, "items": [], "source": "live_oasis", "error": str(exc)}

    def _try_interview_history(self, simulation_id: str) -> Dict[str, Any]:
        """Read prior interview rows from simulation sqlite traces."""
        try:
            rows = SimulationRunner.get_interview_history(
                simulation_id=simulation_id,
                limit=self.config.TRACEABLE_REPORT_MAX_INTERVIEWS,
            )
            items = [
                {
                    "agent_id": row.get("agent_id"),
                    "agent_name": f"agent_{row.get('agent_id')}",
                    "platform": row.get("platform"),
                    "question": row.get("prompt"),
                    "response": row.get("response"),
                    "timestamp": row.get("timestamp"),
                    "source": "interview_history",
                }
                for row in rows
                if row.get("response")
            ]
            return {"success": bool(items), "items": items, "source": "interview_history", "error": None}
        except Exception as exc:
            return {"success": False, "items": [], "source": "interview_history", "error": str(exc)}

    def _try_recent_actions(self, simulation_id: str) -> Dict[str, Any]:
        """Read recent agent actions from run state or actions.jsonl files."""
        try:
            actions = []
            state = SimulationRunner.get_run_state(simulation_id)
            if state:
                actions.extend([item.to_dict() for item in state.recent_actions])

            if not actions:
                actions.extend(self._read_actions_jsonl(simulation_id))

            items = []
            for action in actions[: self.config.TRACEABLE_REPORT_MAX_INTERVIEWS]:
                agent_name = action.get("agent_name") or f"agent_{action.get('agent_id')}"
                text = self._action_summary(action)
                items.append(
                    {
                        "agent_id": action.get("agent_id"),
                        "agent_name": agent_name,
                        "platform": action.get("platform"),
                        "question": "recent simulation behavior",
                        "response": text,
                        "timestamp": action.get("timestamp"),
                        "source": "simulation_actions",
                    }
                )

            return {"success": bool(items), "items": items, "source": "simulation_actions", "error": None}
        except Exception as exc:
            return {"success": False, "items": [], "source": "simulation_actions", "error": str(exc)}

    def _read_actions_jsonl(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Read recent action rows from simulation output files."""
        sim_dir = os.path.join(SimulationRunner.RUN_STATE_DIR, simulation_id)
        paths = [
            os.path.join(sim_dir, "twitter", "actions.jsonl"),
            os.path.join(sim_dir, "reddit", "actions.jsonl"),
            os.path.join(sim_dir, "actions.jsonl"),
        ]
        rows: List[Dict[str, Any]] = []
        for path in paths:
            if not os.path.exists(path):
                continue
            with open(path, "r", encoding="utf-8") as file:
                lines = file.readlines()[-50:]
            for line in reversed(lines):
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(data, dict):
                    rows.append(data)
                if len(rows) >= self.config.TRACEABLE_REPORT_MAX_INTERVIEWS:
                    return rows
        return rows

    @staticmethod
    def _normalize_live_interviews(result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Normalize different live interview response shapes."""
        payload = result.get("result") if isinstance(result, dict) else {}
        results = payload.get("results", payload) if isinstance(payload, dict) else {}
        items = []
        if isinstance(results, dict):
            iterable = results.items()
        elif isinstance(results, list):
            iterable = [(str(index), value) for index, value in enumerate(results)]
        else:
            iterable = []

        for key, value in iterable:
            if isinstance(value, dict):
                response = value.get("response") or value.get("result") or value.get("text")
                timestamp = value.get("timestamp")
            else:
                response = str(value)
                timestamp = None
            if not response:
                continue
            platform, agent_id = ReportToolset._split_interview_key(key)
            items.append(
                {
                    "agent_id": agent_id,
                    "agent_name": f"agent_{agent_id}" if agent_id is not None else str(key),
                    "platform": platform,
                    "question": "live simulation interview",
                    "response": response,
                    "timestamp": timestamp,
                    "source": "live_oasis",
                }
            )
        return items

    @staticmethod
    def _split_interview_key(key: str) -> tuple[str, Optional[int]]:
        """Split keys like twitter_0 into platform and agent id."""
        parts = str(key).split("_")
        if len(parts) >= 2 and parts[-1].isdigit():
            return "_".join(parts[:-1]), int(parts[-1])
        return "", None

    @staticmethod
    def _action_summary(action: Dict[str, Any]) -> str:
        """Render one simulation action as interview-style opinion context."""
        action_type = action.get("action_type") or action.get("action") or "unknown_action"
        result = action.get("result") or ""
        args = action.get("action_args") or action.get("args") or {}
        return f"recent action: {action_type}; args={args}; result={result}"

    @staticmethod
    def _review_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize claim review results."""
        if not results:
            return {"claim_count": 0, "average_confidence": 0.0, "risk_levels": {}}
        confidence = [float(item.get("confidence_score", 0.0)) for item in results]
        risk_levels: Dict[str, int] = {}
        for item in results:
            risk = item.get("risk_level") or "unknown"
            risk_levels[risk] = risk_levels.get(risk, 0) + 1
        return {
            "claim_count": len(results),
            "average_confidence": round(sum(confidence) / len(confidence), 4),
            "risk_levels": risk_levels,
        }

_default_tools = ReportToolset()


def memory_recall_tool(question: str) -> Dict[str, Any]:
    """Tool function: recall long-term memories."""
    return _default_tools.memory_recall_tool(question)


def graph_retrieve_tool(question: str) -> Dict[str, Any]:
    """Tool function: retrieve graph relations."""
    return _default_tools.graph_retrieve_tool(question)


def active_search_tool(question: str) -> Dict[str, Any]:
    """Tool function: run active search."""
    return _default_tools.active_search_tool(question)


def interview_agents_tool(question: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Tool function: interview or read simulation agents."""
    return _default_tools.interview_agents_tool(question, context)


def confidence_review_tool(report_text: str) -> Dict[str, Any]:
    """Tool function: review a draft report."""
    return _default_tools.confidence_review_tool(report_text)


def evidence_trace_tool(context: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Tool function: build evidence trace."""
    return _default_tools.evidence_trace_tool(context)
