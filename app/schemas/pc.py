from pydantic import BaseModel, ConfigDict, Field


class PCBase(BaseModel):
    mac_address: str = Field(
        ..., max_length=17, description="MAC-адрес в формате 00:00:00:00:00:00"
    )
    status: str = Field(default="available")


class PCCreate(PCBase):
    zone_id: int


class PCResponce(PCBase):
    id: int
    zone_id: int
    model_config = ConfigDict(from_attributes=True)
