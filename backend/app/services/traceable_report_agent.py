"""Traceable ReAct-style ReportAgent extension."""

import json
import threading
import time
import traceback
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.llm_client import LLMClient
from ..utils.locale import get_language_instruction, t
from ..utils.logger import get_logger
from .claim_splitter import PLACEHOLDER_KEYS
from .report_tools import ReportToolset

logger = get_logger("mirofish.traceable_report")


class TraceableReportAgent:
    """Coordinate report tools and produce a traceable prediction report."""

    def __init__(self, *, config=Config, tools: Optional[ReportToolset] = None):
        self.config = config
        self.tools = tools or ReportToolset(config=config)

    @staticmethod
    def _run_with_timeout(func, args=(), kwargs=None, timeout=30, default=None):
        """Run func in a thread with a timeout. Returns default if it times out."""
        if kwargs is None:
            kwargs = {}
        result = [default]
        exc = [None]

        def _worker():
            try:
                result[0] = func(*args, **kwargs)
            except Exception as e:
                exc[0] = e

        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        t.join(timeout)
        if t.is_alive():
            logger.warning(f"{func.__name__} timed out after {timeout}s, continuing with default")
            return default
        if exc[0] is not None:
            raise exc[0]
        return result[0]

    def run_traceable_report(self, question: str, options: Optional[Dict[str, Any]] = None, on_progress=None) -> Dict[str, Any]:
        """Run memory, graph, search, interview, review, and report synthesis.

        on_progress(step_name, details) -- optional callback invoked at each step.
        """
        question = (question or "").strip()
        if not question:
            raise ValueError("question is required")

        def _notify(step, details=None):
            if on_progress:
                try:
                    on_progress(step, details or {})
                except Exception:
                    pass

        options = options or {}
        t0 = time.time()
        context: Dict[str, Any] = {
            "question": question,
            "project_id": options.get("project_id"),
            "simulation_id": options.get("simulation_id"),
            "graph_id": options.get("graph_id"),
            "tool_errors": [],
            "report_warnings": [],
        }

        _notify("memory_recall", {"status": "start"})
        try:
            memory_result = self._run_with_timeout(
                self.tools.memory_recall_tool, args=(question,), timeout=30,
                default={"success": False, "items": [], "error": "memory recall timed out"},
            )
            context["memory_used"] = memory_result.get("items", [])
            self._record_tool_error(context, "memory_recall", memory_result)
        except Exception as exc:
            logger.error(f"memory_recall failed: {exc}\n{traceback.format_exc()}")
            raise
        logger.info(f"memory_recall done in {time.time()-t0:.1f}s, count={len(context.get('memory_used', []))}")
        _notify("memory_recall", {"status": "done", "count": len(context.get("memory_used", []))})

        _notify("graph_retrieve", {"status": "start"})
        try:
            graph_result = self._run_with_timeout(
                self.tools.graph_retrieve_tool,
                args=(question,), kwargs={"graph_id": options.get("graph_id")},
                timeout=120,
                default={"success": False, "items": [], "error": "graph retrieve timed out"},
            )
            context["graph_relations_used"] = graph_result.get("items", [])
            self._record_tool_error(context, "graph_retrieve", graph_result)
        except Exception as exc:
            logger.error(f"graph_retrieve failed: {exc}\n{traceback.format_exc()}")
            raise
        logger.info(f"graph_retrieve done in {time.time()-t0:.1f}s, count={len(context.get('graph_relations_used', []))}")
        _notify("graph_retrieve", {"status": "done", "count": len(context.get("graph_relations_used", []))})

        _notify("active_search", {"status": "start"})
        try:
            if bool(options.get("use_active_search", False)):
                search_result = self.tools.active_search_tool(question)
            else:
                search_result = {"success": True, "items": [], "error": None, "skipped": True}
            context["active_search_used"] = search_result.get("items", [])
            self._record_tool_error(context, "active_search", search_result)
        except Exception as exc:
            logger.error(f"active_search failed: {exc}\n{traceback.format_exc()}")
            raise
        logger.info(f"active_search done in {time.time()-t0:.1f}s, count={len(context.get('active_search_used', []))}")
        _notify("active_search", {"status": "done", "count": len(context.get("active_search_used", [])), "skipped": search_result.get("skipped", False)})

        _notify("interview", {"status": "start"})
        try:
            # Run interview with a 60s timeout to prevent hanging on IPC/SQLite
            interview_result = self._run_with_timeout(
                self.tools.interview_agents_tool,
                args=(question, context),
                timeout=60,
                default={"success": False, "items": [], "source": "timeout", "error": "interview timed out after 60s", "skipped": True},
            )
            context["agent_interviews"] = interview_result.get("items", [])
            context["agent_interview_meta"] = {
                "source": interview_result.get("source", ""),
                "simulation_id": interview_result.get("simulation_id"),
                "warnings": interview_result.get("warnings", []),
                "reason": interview_result.get("reason", ""),
                "skipped": interview_result.get("skipped", False),
            }
            self._record_tool_error(context, "interview_agents", interview_result)
        except Exception as exc:
            logger.error(f"interview failed: {exc}\n{traceback.format_exc()}")
            raise
        logger.info(f"interview done in {time.time()-t0:.1f}s, count={len(context.get('agent_interviews', []))}")
        _notify("interview", {"status": "done", "count": len(context.get("agent_interviews", []))})

        _notify("evidence_trace", {"status": "start"})
        try:
            evidence_trace = self.tools.evidence_trace_tool(context)
            context["evidence_trace"] = evidence_trace
        except Exception as exc:
            logger.error(f"evidence_trace failed: {exc}\n{traceback.format_exc()}")
            raise
        logger.info(f"evidence_trace done in {time.time()-t0:.1f}s, count={len(evidence_trace)}")
        _notify("evidence_trace", {"status": "done", "count": len(evidence_trace)})

        _notify("draft_report", {"status": "start"})
        try:
            draft_report = self._run_with_timeout(
                self._generate_initial_report, args=(question, context), timeout=60,
                default="",
            )
            if not draft_report:
                draft_report = self._generate_initial_report_with_rules(question, context)
        except Exception as exc:
            logger.error(f"draft_report failed: {exc}\n{traceback.format_exc()}")
            draft_report = self._generate_initial_report_with_rules(question, context)
        logger.info(f"draft_report done in {time.time()-t0:.1f}s, length={len(draft_report)}")
        _notify("draft_report", {"status": "done", "length": len(draft_report)})

        review_result: Dict[str, Any] = {}
        if bool(options.get("use_review", True)):
            _notify("confidence_review", {"status": "start"})
            try:
                review_result = self._run_with_timeout(
                    self.tools.confidence_review_tool, args=(draft_report,), timeout=60,
                    default={"success": False, "claims": [], "results": [], "summary": "", "error": "confidence review timed out"},
                )
                self._record_tool_error(context, "confidence_review", review_result)
            except Exception as exc:
                logger.error(f"confidence_review failed: {exc}\n{traceback.format_exc()}")
                review_result = {"success": False, "claims": [], "results": [], "summary": "", "error": str(exc)}
            avg_conf = review_result.get("summary", {}).get("average_confidence", 0) if review_result else 0
            logger.info(f"confidence_review done in {time.time()-t0:.1f}s, avg_conf={avg_conf}")
            _notify("confidence_review", {"status": "done", "average_confidence": avg_conf})

        _notify("revise_report", {"status": "start"})
        try:
            final_report = self._revise_report_with_review(draft_report, review_result, context)
        except Exception as exc:
            logger.error(f"revise_report failed: {exc}\n{traceback.format_exc()}")
            raise
        logger.info(f"revise_report done in {time.time()-t0:.1f}s, length={len(final_report)}")
        _notify("revise_report", {"status": "done", "length": len(final_report)})

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
            context.setdefault("report_warnings", []).append("LLM not configured, using rules-based report")
            return self._generate_initial_report_with_rules(question, context)
        try:
            return self._generate_initial_report_with_llm(question, context)
        except Exception as exc:
            context.setdefault("report_warnings", []).append(f"llm draft generation failed: {exc}")
            return self._generate_initial_report_with_rules(question, context)

    def _generate_initial_report_with_llm(self, question: str, context: Dict[str, Any]) -> str:
        """Use the configured OpenAI-compatible LLM for the draft report."""
        client = LLMClient(timeout=self.config.TRACEABLE_REPORT_DRAFT_TIMEOUT_SECONDS, max_retries=0)

        evidence = context.get("evidence_trace", [])
        interviews = context.get("agent_interviews", [])

        # Build evidence summary for prompt context
        evidence_by_source: Dict[str, list] = {}
        for ev in evidence:
            src = ev.get("source_type", "unknown")
            evidence_by_source.setdefault(src, []).append(ev)

        prompt_payload = {
            "question": question,
            "evidence_count": len(evidence),
            "evidence_by_source": {k: len(v) for k, v in evidence_by_source.items()},
            "evidence_trace": evidence,
            "agent_interviews": interviews,
            "tool_errors": context.get("tool_errors", []),
        }
        return client.chat(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"{get_language_instruction()} "
                        "You are a predictive analysis report writing expert. "
                        "Write a traceable prediction report in exactly 5 sections using the provided evidence.\n\n"
                        "REQUIRED STRUCTURE (use these exact section headings):\n"
                        "# 1. 事件概述 (Event Overview)\n"
                        "- Restate the prediction question\n"
                        "- Summarize key background from evidence\n"
                        "- List the number of evidence items from each source type\n\n"
                        "# 2. 多源证据链 (Multi-Source Evidence Chain)\n"
                        "- Organize evidence by source type: graph relations, memory, agent interviews, active search\n"
                        "- Cite evidence IDs like [ev_001] for every factual claim\n"
                        "- Mark agent interviews as opinions, not facts\n"
                        "- Highlight cross-source corroborations or contradictions\n\n"
                        "# 3. 分析性预测 (Analytical Prediction)\n"
                        "- Provide scenario analysis (optimistic / baseline / pessimistic)\n"
                        "- State the most likely outcome with supporting evidence IDs\n"
                        "- Identify key driving factors and trend indicators\n\n"
                        "# 4. 多角色评审与置信度 (Multi-Role Review & Confidence)\n"
                        "- Summarize review findings from fact_checker, supporter, opponent, risk_reviewer, evidence_organizer\n"
                        "- State overall confidence score and its interpretation\n"
                        "- Note any disagreements between reviewers\n\n"
                        "# 5. 不确定性声明 (Uncertainty Statement)\n"
                        "- List specific risk factors and unknown variables\n"
                        "- State evidence gaps and limitations\n"
                        "- Provide confidence boundaries and conditions under which the prediction might change\n\n"
                        "RULES:\n"
                        "- Cite evidence IDs [ev_XXX] for every factual claim\n"
                        "- Do not fabricate sources or evidence\n"
                        "- Treat Agent interviews as opinions, not facts\n"
                        "- Do not contradict known graph relationships\n"
                        "- When evidence is insufficient, explicitly state the gap"
                    ),
                },
                {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
            ],
            temperature=0.2,
            max_tokens=self.config.TRACEABLE_REPORT_MAX_TOKENS,
        )

    def _generate_initial_report_with_rules(self, question: str, context: Dict[str, Any]) -> str:
        """Generate a deterministic 5-section report from real retrieved evidence."""
        evidence = context.get("evidence_trace", [])
        memory = [item for item in evidence if item.get("source_type") == "memory"]
        graph = [item for item in evidence if item.get("source_type") == "graph"]
        search = [item for item in evidence if item.get("source_type") == "active_search"]
        interviews = [item for item in evidence if item.get("source_type") == "agent_interview"]

        source_summary = []
        if graph:
            source_summary.append(f"graph={len(graph)}")
        if memory:
            source_summary.append(f"memory={len(memory)}")
        if interviews:
            source_summary.append(f"interviews={len(interviews)}")
        if search:
            source_summary.append(f"search={len(search)}")
        source_desc = ", ".join(source_summary) if source_summary else "no evidence"

        lines = [
            f"# {t('step4.ruleReportTitle')}",
            "",
            f"## 1. {t('step4.eventOverview', default='事件概述')}",
            "",
            f"**{t('step4.ruleAnalysisQuestion')}**: {question}",
            "",
            f"- {t('step4.evidenceSourcesCount', default='Evidence sources')}: {source_desc}",
            f"- {t('step4.totalEvidenceItems', default='Total evidence items')}: {len(evidence)}",
            "",
        ]

        if evidence:
            ids = ", ".join(item["evidence_id"] for item in evidence[:3])
            lines.append(t('step4.ruleJudgmentWithEvidence', ids=ids))
        else:
            lines.append(t('step4.ruleJudgmentNoEvidence'))

        # Section 2: Multi-source evidence chain
        lines.extend([
            "",
            f"## 2. {t('step4.multiSourceEvidence', default='多源证据链')}",
        ])
        self._append_evidence_lines(lines, t('step4.ruleGraph'), graph)
        self._append_evidence_lines(lines, t('step4.ruleMemory'), memory)
        self._append_evidence_lines(lines, t('step4.ruleAgentInterview'), interviews, opinion=True)
        self._append_evidence_lines(lines, t('step4.ruleActiveSearch'), search)

        # Section 3: Analytical prediction
        lines.extend([
            "",
            f"## 3. {t('step4.analyticalPrediction', default='分析性预测')}",
        ])
        if evidence:
            lines.extend([
                "",
                f"**{t('step4.baselineScenario', default='Baseline scenario')}**: "
                + t('step4.ruleForecastText'),
                "",
                f"**{t('step4.keyFactors', default='Key driving factors')}**:",
            ])
            for item in evidence[:3]:
                lines.append(f"- [{item['evidence_id']}] {item.get('evidence_text', '')[:80]}")
        else:
            lines.append(t('step4.ruleForecastText'))

        # Section 4: Multi-role review & confidence
        review_result = context.get("review_result", {})
        avg_conf = 0
        if review_result:
            summary = review_result.get("summary", {})
            avg_conf = summary.get("average_confidence", 0)

        lines.extend([
            "",
            f"## 4. {t('step4.multiRoleReview', default='多角色评审与置信度')}",
            "",
            f"- {t('step4.overallConfidence', default='Overall confidence')}: {avg_conf:.1%}" if avg_conf else f"- {t('step4.noReviewAvailable', default='Review not yet performed')}",
        ])

        if review_result and review_result.get("results"):
            for role_result in review_result["results"][:5]:
                role = role_result.get("role", "unknown")
                score = role_result.get("score", "N/A")
                lines.append(f"- **{role}**: score={score}")

        # Section 5: Uncertainty statement
        lines.extend([
            "",
            f"## 5. {t('step4.uncertaintyStatement', default='不确定性声明')}",
            "",
            t('step4.ruleUncertaintyText'),
        ])

        if not evidence:
            lines.append(f"- {t('step4.noEvidenceWarning', default='No evidence available — prediction reliability is very low')}")

        if context.get("report_warnings"):
            lines.extend(["", f"### {t('step4.ruleGenerationNotes')}"])
            for warning in context["report_warnings"]:
                lines.append(f"- {warning}")

        if context.get("tool_errors"):
            lines.extend(["", f"### {t('step4.ruleToolLimitations')}"])
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
