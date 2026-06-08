"""Celery application (the worker tier).

Long/expensive work — report rendering, LLM enhancement at scale, evaluation runs —
runs here, off the API request path (architecture §2), so it can't consume request
capacity and scales independently. Redis is the broker + result backend.

`celery -A app.infra.celery_app worker -l info`
"""

from __future__ import annotations

import os

from celery import Celery

_broker = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

celery_app = Celery("advisory", broker=_broker, backend=_backend)
celery_app.conf.update(
    task_acks_late=True,            # don't lose a job if a worker dies mid-render
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_prefetch_multiplier=1,  # fair dispatch for slow PDF/LLM tasks
)
celery_app.autodiscover_tasks(["app.worker"])
