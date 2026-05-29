import logging
from decimal import Decimal

import stripe

from app.core.config import settings

logger = logging.getLogger(__name__)

stripe.api_key = settings.STRIPE_SECRET_KEY


class StripePayService:
    async def create_checkout_session(
        self, amount: Decimal, transaction_id: str, user_email: str
    ) -> str | None:
        try:
            amount_cents = int(amount * 100)

            session = await stripe.checkout.Session.create_async(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price_data": {
                            "currency": "uah",
                            "product_data": {
                                "name": "Пополнение баланса аккаунта",
                                "description": f"Личный счет в системе бронирования ПК. Пользователь: {user_email}",
                            },
                            "unit_amount": amount_cents,
                        },
                        "quantity": 1,
                    }
                ],
                mode="payment",
                client_reference_id=transaction_id,
                success_url=f"{settings.BASE_URL}/profile?status=success",
                cancel_url=f"{settings.BASE_URL}/profile?status=cancelled",
                customer_email=user_email,
            )

            return session.url

        except stripe.StripeError as e:
            logger.error(f"Ошибка при создании Stripe Checkout Session: {e}")
            return None
