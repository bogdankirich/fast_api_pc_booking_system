from datetime import datetime, timedelta, timezone
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, model_validator


class BookingBase(BaseModel):
    start_time: datetime
    end_time: datetime


class BookingCreate(BookingBase):
    pc_id: int
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_times(self) -> "BookingCreate":
        now = datetime.now(timezone.utc)

        if self.start_time < now - timedelta(minutes=1):
            raise ValueError("Time of booking cannot be in a past")
        if self.end_time < self.start_time + timedelta(minutes=15):
            raise ValueError("Minimal time of booking is 15 minutes")
        return self


class BookingResponce(BookingBase):
    id: int
    user_id: int
    pc_id: int
    total_cost: Decimal
    status: str

    model_config = ConfigDict(from_attributes=True)
