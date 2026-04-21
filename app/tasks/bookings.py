import asyncio
import logging
from datetime import datetime, timezone
from typing import cast

from celery import shared_task
from sqlalchemy import CursorResult, update

from app.db.database import async_session_maker
from app.models.bookings import Booking

logger = logging.getLogger(__name__)


async def _expire_bookings_logic():
    now = datetime.now(timezone.utc)

    async with async_session_maker() as session:
        stmt = (
            update(Booking)
            .where(Booking.status == "active", Booking.end_time <= now)
            .values(status="completed")
        )
        result = await session.execute(stmt)
        await session.commit()

        cursor_result = cast(CursorResult, result)
        if cursor_result.rowcount > 0:
            logger.info(
                f"Успешно закрыто просроченных бронирований: {cursor_result.rowcount}"
            )
        else:
            logger.info("Просроченных бронирований не найдено.")


@shared_task(name="check_expired_bookings")
def check_expired_bookings():
    logger.info("Celery: Проверяю истекшие бронирования...")
    asyncio.run(_expire_bookings_logic())
    return "Done"
