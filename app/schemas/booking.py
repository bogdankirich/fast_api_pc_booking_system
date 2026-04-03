from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class BookingBase(BaseModel):
    start_time: datetime
    end_time: datetime


class BookingCreate(BookingBase):
    pc_id: int


class BookingResponce(BookingBase):
    id: int
    user_id: int
    pc_id: int
    total_cost: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)
