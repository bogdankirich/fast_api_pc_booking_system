from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    "pc_club_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.bookings"],
)

celery_app.conf.update(
    timezone="UTC",
    beat_schedule={
        "check-expired-bookings-every-minute": {
            "task": "app.tasks.bookings.check_expired_bookings",
            "schedule": crontab(minute="*"),
        }
    },
)
