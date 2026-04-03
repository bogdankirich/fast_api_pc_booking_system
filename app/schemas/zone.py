from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class ZoneBase(BaseModel):
    name: str
    hourly_rate: Decimal


class ZoneCreate(ZoneBase):
    pass


class ZoneResponce(ZoneBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
