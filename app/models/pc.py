from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.bookings import Booking
    from app.models.zone import Zone


class PC(Base):
    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("zones.id", ondelete="CASCADE"))
    mac_address: Mapped[str] = mapped_column(String(17), unique=True)
    status: Mapped[str] = mapped_column(String(50), default="available")

    zone: Mapped["Zone"] = relationship(back_populates="pcs")
    bookings: Mapped[list["Booking"]] = relationship(
        back_populates="pc", cascade="all, delete-orphan"
    )
