"""Celery application."""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ai_intel",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.analysis"],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)
