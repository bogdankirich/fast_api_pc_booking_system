from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "booking_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.bookings"],
)


celery_app.autodiscover_tasks(["app.tasks"])


celery_app.conf.beat_schedule = {
    "check-expired-bookings-every-minute": {
        "task": "check_expired_bookings",
        "schedule": crontab(minute="*"),
    },
}

celery_app.conf.timezone = "UTC"  # type: ignore
