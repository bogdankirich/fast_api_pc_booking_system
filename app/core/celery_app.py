from celery import Celery
from celery.schedules import crontab

celery_app = Celery(
    "pc_club_worker",
    broker="redis://redis:6379/0",
    backend="redis://redis:6379/0",
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
