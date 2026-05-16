"""Celery and scheduler tasks for enhanced ingestion."""

from .celery_app import celery_app

__all__ = ["celery_app"]
