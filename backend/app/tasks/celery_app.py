"""Celery application."""

from celery import Celery

from app.config import get_settings

settings = get_settings()

# Duplicated from app.tasks.analysis rather than imported: that module imports this one,
# so reading the constant from here at import time would be circular. Keep the two in
# step — test_analysis.py asserts they match.
REAP_INTERVAL_SECONDS = 300

celery_app = Celery(
    "ai_intel",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.analysis", "app.tasks.tools"],
)

celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
    # Beat is what runs the reaper that fails analyses stranded by a killed tool, a
    # crashed worker, or a host restart. Without it nothing recovers those rows, since
    # the chord callback that would normally finish them never arrives.
    beat_schedule={
        "reap-stalled-analyses": {
            "task": "app.tasks.analysis.reap_stalled_analyses",
            "schedule": float(REAP_INTERVAL_SECONDS),
        }
    },
)
