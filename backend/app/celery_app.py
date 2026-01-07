"""Celery application configuration."""

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "codeproof",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.tasks.index_repo", "app.tasks.scan_repo"],
)

# Configuration
celery_app.conf.update(
    # Task execution
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task behavior
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per task
    task_soft_time_limit=540,  # Soft limit 9 minutes

    # Retry behavior
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Worker configuration
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
)
