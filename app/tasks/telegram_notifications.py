import httpx
from celery import shared_task

from app.core.config import (
    settings,
)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="send_booking_reminder",
)
def send_booking_reminder(self, telegram_id: int, pc_number: int, end_time_str: str):
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
        with httpx.Client() as client:
            response = client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return f"Reminder sent to {telegram_id}"

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
