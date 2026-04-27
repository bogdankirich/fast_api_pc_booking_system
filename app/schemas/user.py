from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr


class UserCreate(UserBase):
    password: str = Field(
        ..., min_length=8, max_length=72, description="Password min 8 symbols, max 72"
    )


class UserCreateGoogle(UserBase):
    auth_provider: str = "google"


class UserResponse(UserBase):
    id: int
    balance: Decimal
    role: str
    auth_provider: str

    model_config = ConfigDict(from_attributes=True)
