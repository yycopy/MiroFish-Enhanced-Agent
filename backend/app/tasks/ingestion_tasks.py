"""Celery tasks for active ingestion."""

from sqlalchemy.exc import IntegrityError

from ..db import create_all_tables
from ..models.ingestion import (
    INGESTION_STATUS_FAILED,
    INGESTION_STATUS_FINISHED,
    INGESTION_STATUS_RUNNING,
)
from ..repositories.ingestion_repository import IngestionRepository
from ..repositories.memory_repository import MemoryRepository
from ..services.active_search_service import active_search
from ..services.content_cleaner import clean_documents
from ..services.dedup_service import dedup_documents
from ..services.importance_scorer import calculate_importance
from ..services.memory_store import ChromaUnavailableError, MemoryStore
from ..services.summary_service import summarize_document
from ..services.zep_memory_writer import ZepGraphMemoryUnavailable, ZepMemoryWriter
from ..utils.logger import get_logger
from .celery_app import celery_app


logger = get_logger("mirofish.ingestion")


@celery_app.task(name="app.tasks.ingestion_tasks.run_ingestion_task", bind=True)
def run_ingestion_task(self, task_id: str, keyword: str) -> dict:
    """Run the active ingestion pipeline for one keyword."""
    ingestion_repository = IngestionRepository()
    memory_repository = MemoryRepository()

    try:
        create_all_tables()
        ingestion_repository.update_status(task_id, status=INGESTION_STATUS_RUNNING)

        raw_docs = active_search(keyword)
        clean_docs = clean_documents(raw_docs)
        unique_docs = dedup_documents(clean_docs)

        saved_items = []
        skipped = []
        memory_store = MemoryStore(repository=memory_repository)

        for doc in unique_docs:
            try:
                summary_result = summarize_document(doc)
                importance_score = calculate_importance(doc, summary_result)
                memory_item = _save_to_mysql(
                    doc,
                    summary_result,
                    importance_score,
                    memory_repository,
                )
                chroma_result = _save_to_chroma(memory_item, memory_store)
                zep_result = _try_write_to_zep(memory_item, doc, summary_result)
                if zep_result:
                    memory_repository.mark_written_to_zep(memory_item["id"], True)
                saved_items.append(
                    {
                        "memory_id": memory_item["id"],
                        "title": memory_item.get("title"),
                        "url": memory_item.get("url"),
                        "importance_score": memory_item.get("importance_score"),
                        "chroma_id": chroma_result.get("id") if chroma_result else None,
                        "zep_written": bool(zep_result),
                        "zep_episode_uuid": zep_result.get("episode_uuid") if zep_result else None,
                    }
                )
            except IntegrityError as exc:
                skipped.append({"url": doc.get("url"), "reason": f"duplicate: {exc}"})
            except ChromaUnavailableError as exc:
                skipped.append({"url": doc.get("url"), "reason": f"chroma unavailable: {exc}"})
            except Exception as exc:
                skipped.append({"url": doc.get("url"), "reason": str(exc)})

        result = {
            "task_id": task_id,
            "keyword": keyword,
            "raw_count": len(raw_docs),
            "clean_count": len(clean_docs),
            "unique_count": len(unique_docs),
            "saved_count": len(saved_items),
            "skipped": skipped,
            "items": saved_items,
            "zep_write": "best_effort",
        }
        ingestion_repository.update_status(task_id, status=INGESTION_STATUS_FINISHED)
        return result
    except Exception as exc:
        logger.exception("ingestion task failed: %s", task_id)
        try:
            ingestion_repository.update_status(
                task_id,
                status=INGESTION_STATUS_FAILED,
                error_message=str(exc),
            )
        except Exception:
            logger.exception("failed to update ingestion task status: %s", task_id)
        raise


def _save_to_mysql(doc: dict, summary_result: dict, importance_score: float, repository: MemoryRepository) -> dict:
    """Persist one processed document to MySQL memory tables."""
    memory_item = repository.create_item(
        {
            "source": doc.get("source"),
            "source_type": "active_search",
            "url": doc.get("url"),
            "title": doc.get("title"),
            "raw_text": doc.get("raw_text"),
            "clean_text": doc.get("clean_text"),
            "summary": summary_result.get("summary"),
            "publish_time": doc.get("publish_time"),
            "content_hash": doc.get("content_hash"),
            "importance_score": importance_score,
            "credibility_score": _credibility_score(doc, summary_result),
            "memory_type": "active_search",
        }
    )

    for evidence in summary_result.get("evidence") or []:
        repository.create_evidence(
            memory_item["id"],
            {
                "claim": "; ".join(str(item) for item in summary_result.get("opinions") or []),
                "evidence_text": str(evidence),
                "evidence_type": "active_search_summary",
                "source_url": doc.get("url"),
            },
        )

    return memory_item


def _save_to_chroma(memory_item: dict, memory_store: MemoryStore) -> dict:
    """Write one MySQL memory item into Chroma."""
    return memory_store.save_memory_to_chroma(memory_item)


def _try_write_to_zep(memory_item: dict, doc: dict, summary_result: dict) -> dict | None:
    """Best-effort write to enhanced Zep graph memory.

    Zep is an enrichment path, not the source of truth for ingestion. Missing
    Zep config or write failures must not fail the MySQL/Chroma pipeline.
    """
    payload = {
        **summary_result,
        "id": memory_item.get("id"),
        "mysql_id": memory_item.get("id"),
        "source": memory_item.get("source"),
        "source_url": memory_item.get("url"),
        "url": memory_item.get("url"),
        "publish_time": memory_item.get("publish_time") or doc.get("publish_time"),
        "clean_text": memory_item.get("clean_text"),
    }
    try:
        return ZepMemoryWriter().write_graph_memory(payload)
    except ZepGraphMemoryUnavailable as exc:
        logger.warning("skip zep graph memory write: %s", exc)
    except Exception as exc:
        logger.warning("zep graph memory write failed but ingestion continues: %s", exc)
    return None


def _credibility_score(doc: dict, summary_result: dict) -> float:
    """Compute a simple credibility score until a reviewer agent exists."""
    score = 0.45
    source = (doc.get("source") or "").lower()
    if any(hint in source for hint in ["gov", "official", "news", "company"]):
        score += 0.2
    if summary_result.get("evidence"):
        score += 0.2
    if doc.get("url"):
        score += 0.1
    return max(0.0, min(1.0, round(score, 4)))
