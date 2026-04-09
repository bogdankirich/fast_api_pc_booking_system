import asyncio
import logging
from datetime import datetime, timezone
from typing import cast

from sqlalchemy import CursorResult, update

from app.core.celery_app import celery_app
from app.db.database import async_session_maker, engine
from app.models.bookings import Booking

logger = logging.getLogger(__name__)


async def _expire_bookings_logic():
    now = datetime.now(timezone.utc)
    try:
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
    finally:
        await engine.dispose()


@celery_app.task
def check_expired_bookings():
    logger.warning("Celery работает! Проверяю истекшие бронирования...")
    asyncio.run(_expire_bookings_logic())
    return "Done"
