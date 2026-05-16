"""APScheduler entrypoint for periodic active ingestion."""

import signal
import sys
from typing import List

from apscheduler.schedulers.blocking import BlockingScheduler

from ..config import Config
from ..db import create_all_tables
from ..models.ingestion import INGESTION_STATUS_FAILED
from ..repositories.ingestion_repository import IngestionRepository
from ..utils.logger import get_logger
from .ingestion_tasks import run_ingestion_task


logger = get_logger("mirofish.scheduler")


def parse_keywords(raw_keywords: str) -> List[str]:
    """Parse comma-separated keywords from environment configuration."""
    return [item.strip() for item in (raw_keywords or "").split(",") if item.strip()]


def trigger_ingestion(keyword: str) -> dict:
    """Create an ingestion_task row and send the Celery job to RabbitMQ."""
    repository = IngestionRepository()
    create_all_tables()
    task = repository.create_task(keyword=keyword, task_type="active_search")
    try:
        async_result = run_ingestion_task.delay(task["task_id"], keyword)
        logger.info("scheduled ingestion keyword=%s task_id=%s celery_id=%s", keyword, task["task_id"], async_result.id)
        return {"task": task, "celery_id": async_result.id}
    except Exception as exc:
        repository.update_status(
            task["task_id"],
            status=INGESTION_STATUS_FAILED,
            error_message=f"failed to send celery task: {exc}",
        )
        raise


def build_scheduler() -> BlockingScheduler:
    """Build a blocking scheduler with one interval job per keyword."""
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    keywords = parse_keywords(Config.INGESTION_KEYWORDS)
    interval_seconds = max(30, int(Config.INGESTION_INTERVAL_SECONDS))

    for keyword in keywords:
        scheduler.add_job(
            trigger_ingestion,
            "interval",
            seconds=interval_seconds,
            args=[keyword],
            id=f"active_ingestion_{keyword}",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )

    return scheduler


def main() -> int:
    """Run the APScheduler process."""
    keywords = parse_keywords(Config.INGESTION_KEYWORDS)
    if not keywords:
        logger.warning("no ingestion keywords configured")
        return 1

    scheduler = build_scheduler()

    def _shutdown(_signum, _frame):
        logger.info("stopping ingestion scheduler")
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    logger.info(
        "starting ingestion scheduler keywords=%s interval_seconds=%s",
        keywords,
        Config.INGESTION_INTERVAL_SECONDS,
    )
    scheduler.start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
