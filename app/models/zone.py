from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.pc import PC


class Zone(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    hourly_rate: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    pc_s: Mapped[list["PC"]] = relationship(
        back_populates="zone", cascade="all, delete-orphan"
    )
