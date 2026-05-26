from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.transactions import TransactionStatus, TransactionType


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


class TransactionHistoryResponse(BaseModel):
    id: UUID
    amount: Decimal
    status: TransactionStatus
    type: TransactionType
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
