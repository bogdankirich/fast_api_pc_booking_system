from decimal import Decimal

from pydantic import BaseModel, Field


class TopUpRequest(BaseModel):
    amount: Decimal = Field(
        ..., gt=0, description="Сумма пополнения в гривнах (должна быть больше 0)"
    )


class TopUpResponse(BaseModel):
    transaction_id: str
    payment_url: str


class MonoBankWebhookRequest(BaseModel):
    invoiceId: str
    status: str
    amount: int
    ccy: int
    reference: str
