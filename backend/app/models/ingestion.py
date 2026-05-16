"""ORM model for active ingestion tasks.

The task table records future active-search jobs, cleaning jobs, summarization
jobs, and write-back jobs. Stage 2 only defines the durable structure; Celery
and APScheduler will be wired in later phases.
"""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Index, Integer, String, Text

from ..db import Base


INGESTION_STATUS_PENDING = "pending"
INGESTION_STATUS_RUNNING = "running"
INGESTION_STATUS_FINISHED = "finished"
INGESTION_STATUS_FAILED = "failed"

INGESTION_STATUSES = {
    INGESTION_STATUS_PENDING,
    INGESTION_STATUS_RUNNING,
    INGESTION_STATUS_FINISHED,
    INGESTION_STATUS_FAILED,
}


def utc_now() -> datetime:
    """Return a naive UTC timestamp suitable for MySQL DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class IngestionTask(Base):
    """A durable active-ingestion task record."""

    __tablename__ = "ingestion_task"
    __table_args__ = (
        Index("idx_ingestion_task_status", "status"),
        Index("idx_ingestion_task_type", "task_type"),
        Index("idx_ingestion_task_created_at", "created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), nullable=False, unique=True, index=True)
    keyword = Column(String(255), nullable=True)
    task_type = Column(String(64), nullable=False, default="active_search")
    status = Column(String(32), nullable=False, default=INGESTION_STATUS_PENDING)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=utc_now)
    updated_at = Column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    def to_dict(self) -> dict:
        """Convert the task row into a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "keyword": self.keyword,
            "task_type": self.task_type,
            "status": self.status,
            "error_message": self.error_message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
        }
