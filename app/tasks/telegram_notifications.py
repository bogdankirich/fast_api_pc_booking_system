import asyncio

import httpx
from celery import shared_task
from sqlalchemy import select

from app.core.config import settings
from app.db.database import async_session_maker
from app.models.bookings import Booking


# --- АСИНХРОННАЯ ФУНКЦИЯ ДЛЯ БД ---
async def get_booking_status(booking_id: int) -> str:
    """Быстро достает статус брони из БД"""
    async with async_session_maker() as session:
        result = await session.execute(select(Booking).where(Booking.id == booking_id))
        booking = result.scalar_one_or_none()
        return booking.status if booking else "not_found"


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="send_booking_reminder",
)
def send_booking_reminder(
    self, booking_id: int, telegram_id: int, pc_number: int, end_time_str: str
):

    # 1. ЛЕНИВАЯ ПРОВЕРКА СТАТУСА (Вызываем async функцию в sync среде)
    try:
        status = asyncio.run(get_booking_status(booking_id))
    except Exception as e:
        # Если база данных случайно моргнула, отправляем таску на повтор
        raise self.retry(exc=e)

    # Проверяем, стоит ли отправлять сообщение
    if status == "not_found":
        return f"Skipped: Booking {booking_id} not found."
    if status in ["cancelled", "completed"]:
        return f"Skipped: Booking {booking_id} is {status}. No phantom message."

    # 2. ЕСЛИ ВСЕ ОК - ОТПРАВЛЯЕМ СООБЩЕНИЕ В ТЕЛЕГРАМ
    if not telegram_id:
        return "No telegram_id provided"

    bot_token = settings.TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    text = (
        f"⚠️ <b>Внимание!</b>\n\n"
        f"Время вашей брони за ПК <b>№{pc_number}</b> заканчивается в {end_time_str}.\n"
        f"Пожалуйста, сохраните свои данные или продлите сеанс у администратора."
    )

    payload = {"chat_id": telegram_id, "text": text, "parse_mode": "HTML"}

    try:
        # Здесь мы оставляем синхронный httpx.Client(), так как таска Celery синхронная
        with httpx.Client() as client:
            response = client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return f"Reminder sent to {telegram_id} for booking {booking_id}"

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            return f"Failed: User {telegram_id} blocked the bot."
        raise self.retry(exc=e)
    except httpx.RequestError as e:
        raise self.retry(exc=e)


@shared_task(
    bind=True, max_retries=3, default_retry_delay=10, name="send_payment_success"
)
def send_payment_success_notification(self, telegram_id: int, amount: float):

    if not telegram_id:
        return "No telegram_id provided"

    bot_token = settings.TELEGRAM_BOT_TOKEN
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    text = (
        f"✅ <b>Баланс успешно пополнен!</b>\n\n"
        f"На ваш счет зачислено: <b>{amount:.2f} ₴</b>.\n"
        f"Приятной игры! 🎮"
    )

    keyboard = {
        "inline_keyboard": [
            [{"text": "🖥 Перейти к бронированию", "callback_data": "start_booking"}]
        ]
    }

    payload = {
        "chat_id": telegram_id,
        "text": text,
        "parse_mode": "HTML",
        "reply_markup": keyboard,
    }

    try:
        with httpx.Client() as client:
            response = client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return f"Payment success sent to {telegram_id}"

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            return f"Failed: User {telegram_id} blocked the bot."
        raise self.retry(exc=e)
    except httpx.RequestError as e:
        raise self.retry(exc=e)
