"""
Celery worker for processing investment analysis tasks.
Handles data fetching, metric computation, narrative generation, and PDF rendering.
"""

from celery import Celery
import os

# Initialize Celery
redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
celery_app = Celery("investment_analysis", broker=redis_url, backend=redis_url)

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

if __name__ == "__main__":
    celery_app.start()

