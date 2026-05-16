"""End-to-end demo for the enhanced MiroFish pipeline.

The official run path expects real MySQL, Chroma, LLM, embedding, Zep, and a
real active-search provider to be configured before execution. Zep remains a
best-effort enrichment path and is skipped clearly when not configured.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.config import Config  # noqa: E402


class DemoReportToolset:
    """TraceableReportAgent tools backed by this script's already-built data."""

    def __init__(
        self,
        *,
        recall_results: List[Dict[str, Any]],
        graph_results: List[Dict[str, Any]],
        search_docs: List[Dict[str, Any]],
        review_evidence: Dict[str, List[Dict[str, Any]]],
    ):
        from app.services.report_tools import ReportToolset

        self.base = ReportToolset(config=Config)
        self.recall_results = recall_results
        self.graph_results = graph_results
        self.search_docs = search_docs
        self.review_evidence = review_evidence

    def memory_recall_tool(self, question: str, top_k: Optional[int] = None) -> Dict[str, Any]:
        """Return the recall output produced by step 9."""
        limit = top_k or Config.TRACEABLE_REPORT_MEMORY_TOP_K
        return {"success": True, "items": self.recall_results[:limit], "error": None}

    def graph_retrieve_tool(
        self,
        question: str,
        graph_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Return the graph output produced by step 10."""
        max_items = limit or Config.TRACEABLE_REPORT_GRAPH_LIMIT
        return {"success": True, "items": self.graph_results[:max_items], "error": None}

    def active_search_tool(self, question: str, limit: Optional[int] = None) -> Dict[str, Any]:
        """Return the active search documents produced by step 2."""
        max_items = limit or Config.TRACEABLE_REPORT_MAX_SEARCH_RESULTS
        return {"success": True, "items": self.search_docs[:max_items], "error": None}

    def interview_agents_tool(self, question: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Use the existing safe interview fallback behavior."""
        return self.base.interview_agents_tool(question, context)

    def confidence_review_tool(self, report_text: str) -> Dict[str, Any]:
        """Run phase 6 review with this script's evidence slices."""
        from app.services.claim_splitter import ClaimSplitter
        from app.services.confidence_scorer import ConfidenceScorer
        from app.services.review_agent import ReviewAgent

        splitter = ClaimSplitter(config=Config)
        reviewer = ReviewAgent(config=Config)
        scorer = ConfidenceScorer()
        claims = splitter.split_claims(report_text)
        results = []
        for item in claims:
            role_reviews = reviewer.review_claim(item["claim"], self.review_evidence)
            confidence = scorer.calculate_confidence(role_reviews, self.review_evidence)
            results.append(
                {
                    "claim": item["claim"],
                    "evidence": self.review_evidence,
                    "role_reviews": role_reviews,
                    **confidence,
                }
            )
        return {
            "success": True,
            "claims": claims,
            "results": results,
            "summary": self._summary(results),
            "error": None,
        }

    def evidence_trace_tool(self, context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Delegate trace building to the normal toolset."""
        return self.base.evidence_trace_tool(context)

    @staticmethod
    def _summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Summarize review results for TraceableReportAgent."""
        if not results:
            return {"claim_count": 0, "average_confidence": 0.0, "risk_levels": {}}
        risk_levels: Dict[str, int] = {}
        for item in results:
            risk = item.get("risk_level") or "unknown"
            risk_levels[risk] = risk_levels.get(risk, 0) + 1
        avg = sum(float(item.get("confidence_score", 0.0)) for item in results) / len(results)
        return {"claim_count": len(results), "average_confidence": round(avg, 4), "risk_levels": risk_levels}


def parse_args() -> argparse.Namespace:
    """Parse CLI options."""
    parser = argparse.ArgumentParser(description="Run the enhanced MiroFish e2e demo.")
    parser.add_argument("--keyword", default="方案 X", help="active search keyword")
    parser.add_argument("--question", default="方案 X 后续可能怎么发展？", help="recall/report question")
    parser.add_argument("--claim", default="方案 X 后续可能继续发酵", help="claim for review")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="raise on optional Zep failures instead of continuing with empty graph context",
    )
    parser.add_argument(
        "--use-http-chroma",
        action="store_true",
        help="use CHROMA_HOST/CHROMA_PORT instead of local persistent Chroma",
    )
    return parser.parse_args()


def configure_demo(args: argparse.Namespace) -> None:
    """Apply safe local defaults before service instances are created."""
    os.environ.setdefault("ANONYMIZED_TELEMETRY", "FALSE")
    Config.CHROMA_USE_HTTP = bool(args.use_http_chroma)


def main() -> int:
    """Run the enhanced e2e demo."""
    args = parse_args()
    configure_demo(args)

    print_header("MiroFish enhanced e2e demo")
    print_kv("keyword", args.keyword)
    print_kv("question", args.question)
    print_kv("chroma_mode", "http" if Config.CHROMA_USE_HTTP else "local-persistent")
    print_kv("chroma_collection", Config.CHROMA_COLLECTION_NAME)

    task = create_ingestion_task(args)

    from app.repositories.memory_repository import MemoryRepository

    memory_repository: Any = MemoryRepository()

    raw_docs = run_active_search(args.keyword)
    clean_docs = run_cleaning(raw_docs)
    unique_docs = run_dedup(clean_docs)
    summarized_docs = run_summary_and_importance(unique_docs)
    memory_items = run_memory_write(summarized_docs, memory_repository)
    chroma_results, memory_store = run_chroma_write(memory_items, memory_repository)
    zep_results = run_zep_write(memory_items, summarized_docs, strict=args.strict)
    recall_results = run_memory_recall(args.question, memory_store, memory_repository)
    graph_results = run_graph_retrieve(args.question, strict=args.strict)
    review_evidence, review_result = run_review(args.claim, recall_results, graph_results)
    traceable_report = run_traceable_report(
        question=args.question,
        recall_results=recall_results,
        graph_results=graph_results,
        search_docs=raw_docs,
        review_evidence=review_evidence,
    )

    print_header("demo summary")
    print_kv("task_id", task.get("task_id"))
    print_kv("raw_docs", len(raw_docs))
    print_kv("clean_docs", len(clean_docs))
    print_kv("unique_docs", len(unique_docs))
    print_kv("memory_items", len(memory_items))
    print_kv("chroma_written", len(chroma_results))
    print_kv("zep_written", sum(1 for item in zep_results if item.get("written")))
    print_kv("recall_results", len(recall_results))
    print_kv("graph_results", len(graph_results))
    print_kv("review_confidence", review_result.get("confidence_score"))
    print_kv("report_chars", len(traceable_report.get("report") or ""))
    print_kv("evidence_trace_count", len(traceable_report.get("evidence_trace") or []))
    return 0


def create_ingestion_task(args: argparse.Namespace) -> Dict[str, Any]:
    """Create the ingestion task row in MySQL."""
    print_header("1. create ingestion task")
    from app.db import create_all_tables
    from app.repositories.ingestion_repository import IngestionRepository

    task_id = f"e2e_{uuid.uuid4().hex[:12]}"
    create_all_tables()
    task = IngestionRepository().create_task(keyword=args.keyword, task_type="e2e_demo", task_id=task_id)
    task["_mysql_available"] = True
    print_json("mysql task", task)
    return task


def run_active_search(keyword: str) -> List[Dict[str, Any]]:
    """Run active search."""
    print_header("2. active search")
    from app.services.active_search_service import active_search

    docs = active_search(keyword)
    print_kv("raw_count", len(docs))
    print_json("first_doc", docs[0] if docs else {})
    return docs


def run_cleaning(raw_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Clean text."""
    print_header("3. clean documents")
    from app.services.content_cleaner import clean_documents

    docs = clean_documents(raw_docs)
    print_kv("clean_count", len(docs))
    print_json("first_clean_doc", preview_doc(docs[0]) if docs else {})
    return docs


def run_dedup(clean_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Remove duplicates."""
    print_header("4. dedup documents")
    from app.services.dedup_service import dedup_documents

    docs = dedup_documents(clean_docs)
    print_kv("unique_count", len(docs))
    print_json("content_hashes", [doc.get("content_hash") for doc in docs])
    return docs


def run_summary_and_importance(docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Summarize and score documents."""
    print_header("5. summarize and score")
    from app.services.importance_scorer import calculate_importance
    from app.services.summary_service import summarize_document

    results = []
    for index, doc in enumerate(docs, 1):
        summary = summarize_document(doc)
        importance = calculate_importance(doc, summary)
        row = {"doc": doc, "summary": summary, "importance_score": importance}
        results.append(row)
        print_json(
            f"summary_{index}",
            {
                "title": doc.get("title"),
                "summary": summary.get("summary"),
                "entities": summary.get("entities"),
                "events": summary.get("events"),
                "opinions": summary.get("opinions"),
                "importance_score": importance,
            },
        )
    return results


def run_memory_write(
    summarized_docs: List[Dict[str, Any]],
    repository: Any,
) -> List[Dict[str, Any]]:
    """Write memory items to MySQL."""
    print_header("6. write memory items")
    saved = []
    for row in summarized_docs:
        doc = row["doc"]
        summary = row["summary"]
        item = repository.create_item(
            {
                "source": doc.get("source"),
                "source_type": "active_search",
                "url": doc.get("url"),
                "title": doc.get("title"),
                "raw_text": doc.get("raw_text"),
                "clean_text": doc.get("clean_text"),
                "summary": summary.get("summary"),
                "publish_time": doc.get("publish_time"),
                "content_hash": doc.get("content_hash"),
                "importance_score": row["importance_score"],
                "credibility_score": credibility_score(doc, summary),
                "memory_type": "active_search",
            }
        )
        for evidence in summary.get("evidence") or []:
            repository.create_evidence(
                item["id"],
                {
                    "claim": "; ".join(str(value) for value in summary.get("opinions") or []),
                    "evidence_text": str(evidence),
                    "evidence_type": "e2e_summary",
                    "source_url": doc.get("url"),
                },
            )
        item.update(
            {
                "entities": summary.get("entities"),
                "events": summary.get("events"),
                "opinions": summary.get("opinions"),
                "evidence": summary.get("evidence"),
                "uncertainty": summary.get("uncertainty"),
            }
        )
        saved.append(item)

    print_kv("storage", "mysql")
    print_json("memory_ids", [item.get("id") for item in saved])
    return saved


def run_chroma_write(memory_items: List[Dict[str, Any]], repository: Any) -> tuple[List[Dict[str, Any]], Any]:
    """Write memory items into Chroma."""
    print_header("7. write chroma embeddings")
    from app.services.memory_store import MemoryStore

    store = MemoryStore(repository=repository)
    results = []
    for item in memory_items:
        result = store.save_memory_to_chroma(item)
        results.append(result)
        print_json("chroma_item", result)
    return results, store


def run_zep_write(
    memory_items: List[Dict[str, Any]],
    summarized_docs: List[Dict[str, Any]],
    *,
    strict: bool,
) -> List[Dict[str, Any]]:
    """Try writing graph memory to Zep."""
    print_header("8. try zep graph write")
    from app.services.zep_memory_writer import ZepGraphMemoryUnavailable, ZepMemoryWriter

    results = []
    for item, row in zip(memory_items, summarized_docs):
        payload = {
            **row["summary"],
            **item,
            "mysql_id": item.get("id"),
            "source_url": item.get("url"),
        }
        try:
            result = ZepMemoryWriter().write_graph_memory(payload)
            results.append({"memory_id": item.get("id"), "written": True, "result": result})
            print_json("zep_written", results[-1])
        except ZepGraphMemoryUnavailable as exc:
            print_warning(f"zep skipped for memory_id={item.get('id')}: {exc}")
            results.append({"memory_id": item.get("id"), "written": False, "reason": str(exc)})
        except Exception as exc:
            print_error(f"zep write failed for memory_id={item.get('id')}", exc)
            results.append({"memory_id": item.get("id"), "written": False, "reason": str(exc)})
            if strict:
                raise
    return results


def run_memory_recall(question: str, memory_store: Any, repository: Any) -> List[Dict[str, Any]]:
    """Recall memory through Chroma and repository lookup."""
    print_header("9. memory recall")
    from app.services.memory_retriever import MemoryRetriever

    retriever = MemoryRetriever(store=memory_store, repository=repository)
    results = retriever.recall_memory(question, top_k=5)
    print_kv("recall_count", len(results))
    print_json("recall_results", results)
    return results


def run_graph_retrieve(question: str, *, strict: bool) -> List[Dict[str, Any]]:
    """Retrieve graph context from Zep if configured."""
    print_header("10. graph retrieve")
    from app.services.graph_retriever import GraphRetriever
    from app.services.zep_memory_writer import ZepGraphMemoryUnavailable

    try:
        results = GraphRetriever().graph_retrieve(question, limit=5)
        print_kv("graph_count", len(results))
        print_json("graph_results", results)
        return results
    except ZepGraphMemoryUnavailable as exc:
        print_warning(f"graph retrieve skipped: {exc}")
        return []
    except Exception as exc:
        print_error("graph retrieve failed", exc)
        if strict:
            raise
        return []


def run_review(
    claim: str,
    recall_results: List[Dict[str, Any]],
    graph_results: List[Dict[str, Any]],
) -> tuple[Dict[str, List[Dict[str, Any]]], Dict[str, Any]]:
    """Review one claim with phase 6 services."""
    print_header("11. multi-agent credibility review")
    from app.services.confidence_scorer import ConfidenceScorer
    from app.services.review_agent import ReviewAgent

    evidence = build_review_evidence(claim, recall_results, graph_results)
    role_reviews = ReviewAgent(config=Config).review_claim(claim, evidence)
    confidence = ConfidenceScorer().calculate_confidence(role_reviews, evidence)
    result = {"claim": claim, "evidence": evidence, "role_reviews": role_reviews, **confidence}
    print_json("review_result", result)
    return evidence, result


def run_traceable_report(
    *,
    question: str,
    recall_results: List[Dict[str, Any]],
    graph_results: List[Dict[str, Any]],
    search_docs: List[Dict[str, Any]],
    review_evidence: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Generate traceable report through phase 7 agent."""
    print_header("12. traceable report agent")
    from app.services.traceable_report_agent import TraceableReportAgent

    toolset = DemoReportToolset(
        recall_results=recall_results,
        graph_results=graph_results,
        search_docs=search_docs,
        review_evidence=review_evidence,
    )
    result = TraceableReportAgent(config=Config, tools=toolset).run_traceable_report(
        question,
        options={"use_active_search": True, "use_review": True},
    )
    print_json(
        "traceable_report_summary",
        {
            "report_preview": (result.get("report") or "")[:800],
            "evidence_trace_count": len(result.get("evidence_trace") or []),
            "memory_used": len(result.get("memory_used") or []),
            "graph_relations_used": len(result.get("graph_relations_used") or []),
            "agent_interviews": len(result.get("agent_interviews") or []),
            "review_success": (result.get("review_result") or {}).get("success"),
        },
    )
    return result


def build_review_evidence(
    claim: str,
    recall_results: List[Dict[str, Any]],
    graph_results: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Build evidence slices from e2e recall and graph outputs."""
    supporting = []
    neutral = []
    for item in recall_results:
        supporting.append(
            {
                "type": "memory",
                "text": item.get("summary") or "",
                "source": item.get("source") or "",
                "url": item.get("url") or "",
                "score": item.get("final_score"),
                "reason": "recalled memory is related to the claim",
            }
        )
    for item in graph_results:
        neutral.append(
            {
                "type": "graph",
                "text": item.get("evidence") or "",
                "source": item.get("source") or "",
                "url": item.get("source_url") or "",
                "relation": item.get("relation"),
                "reason": "graph relation is relevant but stance needs verification",
            }
        )
    return {
        "supporting_evidence": supporting,
        "opposing_evidence": [],
        "neutral_evidence": neutral,
    }


def credibility_score(doc: Dict[str, Any], summary: Dict[str, Any]) -> float:
    """Compute the same simple credibility style as the ingestion task."""
    score = 0.45
    source = (doc.get("source") or "").lower()
    if any(hint in source for hint in ["gov", "official", "news", "company"]):
        score += 0.2
    if summary.get("evidence"):
        score += 0.2
    if doc.get("url"):
        score += 0.1
    return max(0.0, min(1.0, round(score, 4)))


def preview_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return a short preview for logs."""
    return {
        "title": doc.get("title"),
        "url": doc.get("url"),
        "source": doc.get("source"),
        "publish_time": doc.get("publish_time"),
        "clean_text": (doc.get("clean_text") or "")[:200],
    }


def print_header(title: str) -> None:
    """Print a clear section header."""
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")


def print_kv(key: str, value: Any) -> None:
    """Print one key-value line."""
    print(f"[info] {key}: {value}")


def print_json(label: str, value: Any) -> None:
    """Print compact JSON with Chinese preserved."""
    print(f"[data] {label}:")
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def print_warning(message: str) -> None:
    """Print a warning line."""
    print(f"[warning] {message}")


def print_error(message: str, exc: BaseException) -> None:
    """Print an error with traceback so failures are visible."""
    print(f"[error] {message}: {exc}")
    print(traceback.format_exc())


if __name__ == "__main__":
    raise SystemExit(main())
