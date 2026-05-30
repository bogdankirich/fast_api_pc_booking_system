import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import cast

from celery import shared_task
from sqlalchemy import CursorResult, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.models.transactions import Transaction, TransactionStatus

logger = logging.getLogger(__name__)


async def _cleanup_pending_transactions_logic():
    task_engine = create_async_engine(
        settings.DATABASE_URL, echo=False, poolclass=NullPool
    )
    task_session_maker = async_sessionmaker(
        bind=task_engine, class_=AsyncSession, expire_on_commit=False
    )
    expiration_time = datetime.now(timezone.utc) - timedelta(minutes=30)

    try:
        async with task_session_maker() as session:
            stmt = (
                update(Transaction)
                .where(
                    Transaction.status == TransactionStatus.PENDING,
                    Transaction.created_at <= expiration_time,
                )
                .values(status=TransactionStatus.FAILED)
            )
            result = await session.execute(stmt)
            await session.commit()

            cursor_result = cast(CursorResult, result)
            if cursor_result.rowcount > 0:
                logger.info(
                    f"Успешно отменено зависших транзакций: {cursor_result.rowcount}"
                )
            else:
                logger.info("Зависших PENDING транзакций не найдено.")

    except Exception as e:
        logger.error(f"Ошибка при очистке транзакций: {e}")
    finally:
        await task_engine.dispose()


@shared_task(name="cleanup_pending_transactions")
def cleanup_pending_transactions():
    logger.info("Celery: Запуск проверки зависших PENDING транзакций...")
    asyncio.run(_cleanup_pending_transactions_logic())
    return "Done"
