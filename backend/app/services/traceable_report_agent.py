"""Traceable ReAct-style ReportAgent extension."""

import json
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction, t
from .claim_splitter import PLACEHOLDER_KEYS
from .report_tools import ReportToolset


class TraceableReportAgent:
    """Coordinate report tools and produce a traceable prediction report."""

    def __init__(self, *, config=Config, tools: Optional[ReportToolset] = None):
        self.config = config
        self.tools = tools or ReportToolset(config=config)

    def run_traceable_report(self, question: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run memory, graph, search, interview, review, and report synthesis."""
        question = (question or "").strip()
        if not question:
            raise ValueError("question is required")

        options = options or {}
        context: Dict[str, Any] = {
            "question": question,
            "project_id": options.get("project_id"),
            "simulation_id": options.get("simulation_id"),
            "graph_id": options.get("graph_id"),
            "tool_errors": [],
            "report_warnings": [],
        }

        memory_result = self.tools.memory_recall_tool(question)
        context["memory_used"] = memory_result.get("items", [])
        self._record_tool_error(context, "memory_recall", memory_result)

        graph_result = self.tools.graph_retrieve_tool(question, graph_id=options.get("graph_id"))
        context["graph_relations_used"] = graph_result.get("items", [])
        self._record_tool_error(context, "graph_retrieve", graph_result)

        if bool(options.get("use_active_search", False)):
            search_result = self.tools.active_search_tool(question)
        else:
            search_result = {"success": True, "items": [], "error": None, "skipped": True}
        context["active_search_used"] = search_result.get("items", [])
        self._record_tool_error(context, "active_search", search_result)

        interview_result = self.tools.interview_agents_tool(question, context)
        context["agent_interviews"] = interview_result.get("items", [])
        context["agent_interview_meta"] = {
            "source": interview_result.get("source", ""),
            "simulation_id": interview_result.get("simulation_id"),
            "warnings": interview_result.get("warnings", []),
            "reason": interview_result.get("reason", ""),
            "skipped": interview_result.get("skipped", False),
        }
        self._record_tool_error(context, "interview_agents", interview_result)

        evidence_trace = self.tools.evidence_trace_tool(context)
        context["evidence_trace"] = evidence_trace

        draft_report = self._generate_initial_report(question, context)

        review_result: Dict[str, Any] = {}
        if bool(options.get("use_review", True)):
            review_result = self.tools.confidence_review_tool(draft_report)
            self._record_tool_error(context, "confidence_review", review_result)

        final_report = self._revise_report_with_review(draft_report, review_result, context)

        return {
            "report": final_report,
            "evidence_trace": evidence_trace,
            "memory_used": context["memory_used"],
            "graph_relations_used": context["graph_relations_used"],
            "active_search_used": context["active_search_used"],
            "agent_interviews": context["agent_interviews"],
            "agent_interview_meta": context["agent_interview_meta"],
            "review_result": review_result,
            "tool_errors": context["tool_errors"],
            "report_warnings": context["report_warnings"],
            "project_id": context.get("project_id"),
            "simulation_id": context.get("simulation_id") or context.get("agent_interview_meta", {}).get("simulation_id"),
        }

    def _generate_initial_report(self, question: str, context: Dict[str, Any]) -> str:
        """Generate a report with LLM first, then deterministic evidence fallback."""
        if self._missing_llm_config():
            raise RuntimeError("LLM_API_KEY or OPENAI_API_KEY is required for traceable report generation")
        try:
            return self._generate_initial_report_with_llm(question, context)
        except Exception as exc:
            context.setdefault("report_warnings", []).append(f"llm draft generation failed: {exc}")
            return self._generate_initial_report_with_rules(question, context)

    def _generate_initial_report_with_llm(self, question: str, context: Dict[str, Any]) -> str:
        """Use the configured OpenAI-compatible LLM for the draft report."""
        client = LLMClient(timeout=self.config.TRACEABLE_REPORT_DRAFT_TIMEOUT_SECONDS, max_retries=0)
        prompt_payload = {
            "question": question,
            "evidence_trace": context.get("evidence_trace", []),
            "agent_interviews": context.get("agent_interviews", []),
            "tool_errors": context.get("tool_errors", []),
        }
        return client.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{get_language_instruction()} "
                        "You are a predictive analysis report writing expert. "
                        "Write a traceable prediction report using only the provided evidence, "
                        "citing evidence IDs like [ev_001]. "
                        "Clearly mark uncertainty when evidence is insufficient. "
                        "Do not fabricate sources. Treat Agent interviews as opinions, not facts. "
                        "Do not contradict known graph relationships."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=self.config.TRACEABLE_REPORT_MAX_TOKENS,
        )

    def _generate_initial_report_with_rules(self, question: str, context: Dict[str, Any]) -> str:
        """Generate a deterministic report from real retrieved evidence."""
        evidence = context.get("evidence_trace", [])
        memory = [item for item in evidence if item.get("source_type") == "memory"]
        graph = [item for item in evidence if item.get("source_type") == "graph"]
        search = [item for item in evidence if item.get("source_type") == "active_search"]
        interviews = [item for item in evidence if item.get("source_type") == "agent_interview"]

        lines = [
            f"# {t('step4.ruleReportTitle')}",
            "",
            f"## {t('step4.ruleAnalysisQuestion')}",
            question,
            "",
            f"## {t('step4.ruleCoreJudgment')}",
        ]

        if evidence:
            ids = ", ".join(item["evidence_id"] for item in evidence[:3])
            lines.append(t('step4.ruleJudgmentWithEvidence', ids=ids))
        else:
            lines.append(t('step4.ruleJudgmentNoEvidence'))

        lines.extend(["", f"## {t('step4.ruleEvidence')}"])
        self._append_evidence_lines(lines, t('step4.ruleMemory'), memory)
        self._append_evidence_lines(lines, t('step4.ruleGraph'), graph)
        self._append_evidence_lines(lines, t('step4.ruleActiveSearch'), search)
        self._append_evidence_lines(lines, t('step4.ruleAgentInterview'), interviews, opinion=True)

        lines.extend(
            [
                "",
                f"## {t('step4.ruleForecast')}",
                t('step4.ruleForecastText'),
                "",
                f"## {t('step4.ruleUncertainty')}",
                t('step4.ruleUncertaintyText'),
            ]
        )

        if context.get("report_warnings"):
            lines.extend(["", f"## {t('step4.ruleGenerationNotes')}"])
            for warning in context["report_warnings"]:
                lines.append(f"- {warning}")

        if context.get("tool_errors"):
            lines.extend(["", f"## {t('step4.ruleToolLimitations')}"])
            for error in context["tool_errors"]:
                lines.append(f"- {error.get('tool')}: {error.get('error')}")

        return "\n".join(lines)

    def _revise_report_with_review(
        self,
        draft_report: str,
        review_result: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """Revise or annotate the draft with review findings."""
        if not review_result:
            return draft_report

        if review_result.get("success") and self.config.TRACEABLE_REPORT_REVISE_WITH_LLM:
            try:
                return self._revise_report_with_llm(draft_report, review_result)
            except Exception as exc:
                context.setdefault("report_warnings", []).append(f"llm report revision failed: {exc}")

        summary = review_result.get("summary") or {}
        average_confidence = summary.get("average_confidence", 0.0)
        risk_levels = summary.get("risk_levels", {})
        addon = [
            "",
            f"## {t('step4.ruleConfidenceReview')}",
            t('step4.ruleReviewSummary', confidence=average_confidence, risks=risk_levels),
        ]

        if risk_levels.get("high") or average_confidence < 0.6:
            addon.append(t('step4.ruleReviewHighRisk'))
        else:
            addon.append(t('step4.ruleReviewLowRisk'))

        if review_result.get("error"):
            addon.append(f"Review tool error: {review_result['error']}")

        return draft_report + "\n" + "\n".join(addon)

    def _revise_report_with_llm(self, draft_report: str, review_result: Dict[str, Any]) -> str:
        """Use LLM to revise the draft according to review findings."""
        client = LLMClient()
        payload = {"draft_report": draft_report, "review_result": review_result}
        return client.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{get_language_instruction()} "
                        "Revise the report according to review findings. "
                        "Keep evidence IDs. Tone down overconfident claims. "
                        "Add uncertainty notes where needed. Do not add new sources."
                    ),
                },
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=self.config.TRACEABLE_REPORT_MAX_TOKENS,
        )

    @staticmethod
    def _append_evidence_lines(
        lines: List[str],
        label: str,
        items: List[Dict[str, Any]],
        *,
        opinion: bool = False,
    ) -> None:
        """Append evidence bullets with ids."""
        if not items:
            lines.append(f"- {label}: {t('step4.ruleNoEvidence')}")
            return
        for item in items[:5]:
            prefix = t('step4.ruleOpinion') if opinion else t('step4.ruleEvidencePrefix')
            text = item.get("evidence_text", "")
            source = item.get("source", "")
            url = item.get("url", "")
            lines.append(f"- {label}{prefix} {item['evidence_id']}: {text} {t('step4.ruleSource')}={source} {t('step4.ruleUrl')}={url}")

    @staticmethod
    def _record_tool_error(context: Dict[str, Any], tool_name: str, result: Dict[str, Any]) -> None:
        """Store non-fatal tool errors in the report context."""
        if result.get("success", False) or result.get("skipped", False):
            return
        error = result.get("error")
        if error:
            context.setdefault("tool_errors", []).append({"tool": tool_name, "error": error})

    def _missing_llm_config(self) -> bool:
        """Return true when LLM credentials are missing or placeholders."""
        api_key = (self.config.LLM_API_KEY or self.config.OPENAI_API_KEY or "").strip().lower()
        return api_key in PLACEHOLDER_KEYS


def run_traceable_report(question: str, options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convenience function for API and tests."""
    return TraceableReportAgent().run_traceable_report(question, options=options)
