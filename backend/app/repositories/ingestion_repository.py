"""Repository methods for ingestion task records."""

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select

from ..db import create_all_tables, session_scope
from ..models.ingestion import (
    INGESTION_STATUS_FAILED,
    INGESTION_STATUS_FINISHED,
    INGESTION_STATUS_PENDING,
    INGESTION_STATUS_RUNNING,
    INGESTION_STATUSES,
    IngestionTask,
)


def utc_now() -> datetime:
    """Return a naive UTC timestamp suitable for MySQL DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class IngestionRepository:
    """Encapsulates CRUD access to ingestion_task."""

    def ensure_schema(self) -> None:
        """Create ingestion tables if the configured MySQL database is reachable."""
        create_all_tables()

    def create_task(
        self,
        *,
        keyword: Optional[str] = None,
        task_type: str = "active_search",
        task_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a pending ingestion task."""
        task = IngestionTask(
            task_id=task_id or f"ing_{uuid.uuid4().hex}",
            keyword=keyword,
            task_type=task_type,
            status=INGESTION_STATUS_PENDING,
        )

        with session_scope() as session:
            session.add(task)
            session.flush()
            return task.to_dict()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get an ingestion task by public task_id."""
        statement = select(IngestionTask).where(IngestionTask.task_id == task_id)
        with session_scope() as session:
            task = session.execute(statement).scalar_one_or_none()
            if task is None:
                return None
            return task.to_dict()

    def list_tasks(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List ingestion tasks with optional status filtering."""
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))

        statement = select(IngestionTask).order_by(IngestionTask.created_at.desc())
        if status:
            statement = statement.where(IngestionTask.status == status)
        statement = statement.limit(limit).offset(offset)

        with session_scope() as session:
            rows = session.execute(statement).scalars().all()
            return [task.to_dict() for task in rows]

    def update_status(
        self,
        task_id: str,
        *,
        status: str,
        error_message: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update an ingestion task status and timestamps."""
        if status not in INGESTION_STATUSES:
            raise ValueError(f"invalid ingestion status: {status}")

        statement = select(IngestionTask).where(IngestionTask.task_id == task_id)
        with session_scope() as session:
            task = session.execute(statement).scalar_one_or_none()
            if task is None:
                return None

            task.status = status
            task.error_message = error_message
            if status == INGESTION_STATUS_RUNNING and task.started_at is None:
                task.started_at = utc_now()
            if status in {INGESTION_STATUS_FINISHED, INGESTION_STATUS_FAILED}:
                task.finished_at = utc_now()
            session.flush()
            return task.to_dict()

    def reset_for_retry(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Reset a failed task back to pending before it is sent to Celery again."""
        statement = select(IngestionTask).where(IngestionTask.task_id == task_id)
        with session_scope() as session:
            task = session.execute(statement).scalar_one_or_none()
            if task is None:
                return None
            task.status = INGESTION_STATUS_PENDING
            task.error_message = None
            task.started_at = None
            task.finished_at = None
            session.flush()
            return task.to_dict()
