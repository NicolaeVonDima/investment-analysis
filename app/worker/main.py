"""
Celery worker for processing investment analysis tasks.
Handles data fetching, metric computation, narrative generation, and PDF rendering.
"""

from celery import Celery
from celery.schedules import crontab
import os

# Initialize Celery
_always_eager = os.getenv("CELERY_ALWAYS_EAGER", "").strip() in {"1", "true", "True", "yes", "YES"}
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_broker_url = "memory://" if _always_eager else redis_url
_result_backend = "cache+memory://" if _always_eager else redis_url
celery_app = Celery("investment_analysis", broker=_broker_url, backend=_result_backend)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes
    task_soft_time_limit=240,  # 4 minutes
)

# Ensure task modules are imported so Celery registers them.
from app.worker import tasks as _tasks  # noqa: F401

if _always_eager:
    # Run tasks inline when no broker is available.
    # Do not propagate task exceptions into the web request path; mimic async behavior.
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=False, task_store_eager_result=False)

# Watchlist global refresh schedule (admin-configured via env).
# Default: daily at 02:00 UTC.
_refresh_hour = int(os.getenv("WATCHLIST_REFRESH_HOUR", "2"))
_refresh_minute = int(os.getenv("WATCHLIST_REFRESH_MINUTE", "0"))
_sec_refresh_hour = int(os.getenv("WATCHLIST_SEC_REFRESH_HOUR", "3"))
_sec_refresh_minute = int(os.getenv("WATCHLIST_SEC_REFRESH_MINUTE", "15"))
celery_app.conf.beat_schedule = {
    "refresh_watchlist_universe_daily": {
        "task": "refresh_watchlist_universe",
        "schedule": crontab(minute=_refresh_minute, hour=_refresh_hour),
    },
    "refresh_sec_watchlist_universe_daily": {
        "task": "refresh_sec_watchlist_universe",
        "schedule": crontab(minute=_sec_refresh_minute, hour=_sec_refresh_hour),
    },
}

if __name__ == "__main__":
    celery_app.start()
