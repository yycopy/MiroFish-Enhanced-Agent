"""Celery application configured with RabbitMQ as broker."""

from celery import Celery

from ..config import Config


def _result_backend():
    """Return a Celery result backend or None when task state is stored in MySQL."""
    value = (Config.CELERY_RESULT_BACKEND or "").strip()
    if value.lower() in {"", "none", "null", "disabled", "disabled://"}:
        return None
    return value


celery_app = Celery(
    "mirofish_ingestion",
    broker=Config.CELERY_BROKER_URL,
    backend=_result_backend(),
    include=["app.tasks.ingestion_tasks"],
)

celery_app.conf.update(
    accept_content=["json"],
    result_serializer="json",
    task_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=Config.CELERY_TASK_TIME_LIMIT,
    task_always_eager=Config.CELERY_TASK_ALWAYS_EAGER,
    task_publish_retry=False,
    broker_connection_timeout=Config.CELERY_BROKER_CONNECTION_TIMEOUT,
    broker_connection_retry_on_startup=True,
)

# Celery's CLI can discover either ``celery_app`` or ``app`` from this module.
app = celery_app
