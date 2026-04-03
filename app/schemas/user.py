from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str


class UserResponce(UserBase):
    id: int
    balance: Decimal
    role: str

    model_config = ConfigDict(from_attributes=True)
