import logging
from decimal import Decimal

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class MonoPayService:
    def __init__(self):
        self.api_url = "https://api.monobank.ua/api/merchant/invoice/create"
        self.headers = {
            "X-Token": settings.MONOBANK_API_TOKEN,
            "Content-Type": "application/json",
        }

    async def create_invoice(
        self, amount: Decimal, order_id: str, description: str
    ) -> str | None:

        if settings.MONOBANK_API_TOKEN == "test_token_12345":
            logger.info(
                f"MOCK: Симуляция создания платежа в Монобанке для заказа {order_id}"
            )
            # Возвращаем фейковую ссылку для фронтенда
            return f"https://mock-pay.monobank.ua/checkout/{order_id}"
        amount_cents = int(amount * 100)
        webhook_url = f"{settings.BASE_URL}/api/v1/payments/webhook/monobank"

        payload = {
            "amount": amount_cents,
            "ccy": 980,
            "merchantPaymInfo": {
                "reference": order_id,
                "destination": description,
            },
            "redirectUrl": f"{settings.BASE_URL}/profile",
            "webHookUrl": webhook_url,
        }

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.api_url, json=payload, headers=self.headers
                )
                response.raise_for_status()
                data = response.json()
                return data.get("pageUrl")

            except httpx.HTTPError as e:
                logger.error(f"Ошибка при создании инвойса Monobank: {e}")
                return None
