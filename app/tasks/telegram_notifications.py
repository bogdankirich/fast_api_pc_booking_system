import httpx
from celery import shared_task

from app.core.config import (
    settings,  # Убедись, что TELEGRAM_BOT_TOKEN добавлен в pydantic настройки
)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # Если Телеграм упал, повторить через минуту
    name="send_booking_reminder",
)
def send_booking_reminder(self, telegram_id: int, pc_number: int, end_time_str: str):
    """
    Отправляет уведомление в Telegram за 15 минут до конца брони.
    """
    # Если юзер не привязал телеграм, просто выходим
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

    # Важно: внутри Celery лучше использовать синхронный httpx.Client,
    # так как Celery по умолчанию работает с синхронным кодом.
    try:
        with httpx.Client() as client:
            response = client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return f"Reminder sent to {telegram_id}"

    except httpx.HTTPStatusError as e:
        # Если юзер заблокировал бота, Телеграм вернет 403. Логируем это.
        if e.response.status_code == 403:
            return f"Failed: User {telegram_id} blocked the bot."
        # Для других ошибок (500) делаем ретрай
        raise self.retry(exc=e)
    except httpx.RequestError as e:
        # Ошибка сети
        raise self.retry(exc=e)
