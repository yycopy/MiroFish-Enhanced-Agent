"""Per-project dynamic ingestion scheduler.

Unlike the static APScheduler entrypoint (which reads keywords from .env),
this manager allows each project to start/stop ingestion with keywords
extracted from the project's own seed materials.

Lifecycle:
  Step1 upload → extract keywords from seed materials
  Step2 prepare → call start_ingestion(project_id, keywords, interval_seconds)
  Step3 simulation runs → ingestion fires periodically
  Step3 simulation ends → call stop_ingestion(project_id)
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..config import Config
from ..db import create_all_tables
from ..repositories.ingestion_repository import IngestionRepository
from ..utils.logger import get_logger

logger = get_logger("mirofish.project_ingestion")


@dataclass
class ProjectIngestion:
    """State for one project's active ingestion."""
    project_id: str
    keywords: List[str]
    interval_seconds: int
    max_results: int
    started_at: float
    total_runs: int = 0
    last_run_at: Optional[float] = None
    running: bool = True


class ProjectIngestionManager:
    """Thread-safe singleton managing per-project periodic ingestion."""

    _instance: Optional["ProjectIngestionManager"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._ingestions: Dict[str, ProjectIngestion] = {}
        self._timers: Dict[str, threading.Timer] = {}
        self._repository = IngestionRepository()

    @classmethod
    def instance(cls) -> "ProjectIngestionManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ── Public API ──────────────────────────────────────────

    def start_ingestion(
        self,
        project_id: str,
        keywords: List[str],
        *,
        interval_seconds: Optional[int] = None,
        max_results: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Start periodic ingestion for a project.

        Args:
            project_id: The project to associate ingestion with.
            keywords: Search keywords extracted from seed materials.
            interval_seconds: Seconds between each search cycle.
            max_results: Max results per keyword per cycle.

        Returns:
            Status dict.
        """
        project_id = str(project_id).strip()
        if not project_id:
            raise ValueError("project_id is required")

        keywords = [k.strip() for k in (keywords or []) if k.strip()]
        if not keywords:
            return {
                "success": False,
                "error": "no keywords to search",
                "project_id": project_id,
            }

        interval = max(
            60,
            int(interval_seconds or Config.INGESTION_INTERVAL_SECONDS),
        )
        max_res = max(1, int(max_results or Config.ACTIVE_SEARCH_MAX_RESULTS))

        # Stop any existing ingestion for this project
        self.stop_ingestion(project_id)

        ingestion = ProjectIngestion(
            project_id=project_id,
            keywords=keywords,
            interval_seconds=interval,
            max_results=max_res,
            started_at=time.time(),
        )
        self._ingestions[project_id] = ingestion

        # Run first search immediately, then schedule periodic runs
        logger.info(
            "启动项目采集: project=%s keywords=%s interval=%ds",
            project_id, keywords, interval,
        )

        self._schedule_next(project_id, delay=0)

        return {
            "success": True,
            "project_id": project_id,
            "keywords": keywords,
            "interval_seconds": interval,
            "status": "started",
        }

    def stop_ingestion(self, project_id: str) -> Dict[str, Any]:
        """Stop periodic ingestion for a project."""
        project_id = str(project_id).strip()
        ingestion = self._ingestions.pop(project_id, None)
        timer = self._timers.pop(project_id, None)
        if timer:
            timer.cancel()

        if ingestion:
            ingestion.running = False
            logger.info(
                "停止项目采集: project=%s total_runs=%d",
                project_id, ingestion.total_runs,
            )
            return {
                "success": True,
                "project_id": project_id,
                "total_runs": ingestion.total_runs,
                "status": "stopped",
            }
        return {
            "success": True,
            "project_id": project_id,
            "status": "not_running",
        }

    def get_status(self, project_id: str) -> Dict[str, Any]:
        """Return the current ingestion status for a project."""
        project_id = str(project_id).strip()
        ingestion = self._ingestions.get(project_id)
        if not ingestion:
            return {
                "success": True,
                "project_id": project_id,
                "active": False,
            }
        return {
            "success": True,
            "project_id": project_id,
            "active": ingestion.running,
            "keywords": ingestion.keywords,
            "interval_seconds": ingestion.interval_seconds,
            "total_runs": ingestion.total_runs,
            "started_at": ingestion.started_at,
            "last_run_at": ingestion.last_run_at,
        }

    def stop_all(self) -> None:
        """Stop all active ingestions (for server shutdown)."""
        for project_id in list(self._ingestions):
            self.stop_ingestion(project_id)

    # ── Internal scheduling ─────────────────────────────────

    def _schedule_next(self, project_id: str, delay: float) -> None:
        """Schedule the next ingestion run for a project."""
        ingestion = self._ingestions.get(project_id)
        if not ingestion or not ingestion.running:
            return

        timer = threading.Timer(
            delay if delay > 0 else ingestion.interval_seconds,
            self._run_and_reschedule,
            args=[project_id],
        )
        timer.daemon = True
        self._timers[project_id] = timer
        timer.start()

    def _run_and_reschedule(self, project_id: str) -> None:
        """Execute one ingestion cycle and schedule the next."""
        ingestion = self._ingestions.get(project_id)
        if not ingestion or not ingestion.running:
            return

        try:
            self._run_ingestion_cycle(ingestion)
        except Exception as exc:
            logger.error(
                "项目采集异常: project=%s error=%s", project_id, exc
            )

        # Schedule next run
        self._schedule_next(project_id, ingestion.interval_seconds)

    def _run_ingestion_cycle(self, ingestion: ProjectIngestion) -> None:
        """Execute one full ingestion cycle: search → clean → dedup → store."""
        from .active_search_service import active_search
        from .content_cleaner import clean_documents
        from .dedup_service import dedup_documents
        from .importance_scorer import calculate_importance
        from .memory_store import MemoryStore
        from .summary_service import summarize_document
        from ..repositories.memory_repository import MemoryRepository
        from sqlalchemy.exc import IntegrityError

        create_all_tables()
        memory_repo = MemoryRepository()
        memory_store = MemoryStore(repository=memory_repo)

        saved_total = 0
        for keyword in ingestion.keywords:
            try:
                raw_docs = active_search(keyword)
                clean_docs = clean_documents(raw_docs)
                unique_docs = dedup_documents(clean_docs)

                for doc in unique_docs[: ingestion.max_results]:
                    try:
                        summary = summarize_document(doc)
                        importance = calculate_importance(doc, summary)
                        item = memory_repo.create_item({
                            "source": doc.get("source"),
                            "source_type": "active_search",
                            "url": doc.get("url"),
                            "title": doc.get("title"),
                            "raw_text": doc.get("raw_text"),
                            "clean_text": doc.get("clean_text"),
                            "summary": summary.get("summary"),
                            "publish_time": doc.get("publish_time"),
                            "content_hash": doc.get("content_hash"),
                            "importance_score": importance,
                            "credibility_score": 0.5,
                            "memory_type": "active_search",
                        })

                        # Evidence
                        for evidence in summary.get("evidence") or []:
                            memory_repo.create_evidence(item["id"], {
                                "claim": (
                                    "; ".join(str(e) for e in summary.get("opinions") or [])
                                ),
                                "evidence_text": str(evidence),
                                "evidence_type": "active_search",
                                "source_url": doc.get("url"),
                            })

                        # Chroma
                        try:
                            memory_store.save_memory_to_chroma(item)
                        except Exception:
                            pass

                        saved_total += 1
                    except IntegrityError:
                        continue
                    except Exception as exc:
                        logger.warning(
                            "ingestion doc error keyword=%s: %s", keyword, exc
                        )
                        continue

            except Exception as exc:
                logger.warning(
                    "ingestion keyword error keyword=%s: %s", keyword, exc
                )
                continue

        ingestion.total_runs += 1
        ingestion.last_run_at = time.time()
        logger.info(
            "项目采集周期完成: project=%s run=%d saved=%d",
            ingestion.project_id, ingestion.total_runs, saved_total,
        )
