from datetime import datetime
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookings import Booking
from app.repositories.base import BaseRepository
from app.schemas.booking import BookingCreate


class BookingRepository(BaseRepository[Booking, BookingCreate]):
    def __init__(self) -> None:
        super().__init__(Booking)

    async def get_active_by_user(
        self, db: AsyncSession, *, user_id: int, skip: int = 0, limit: int = 100
    ) -> Sequence[Booking]:
        stmt = (
            select(Booking)
            .where(Booking.user_id == user_id, Booking.status == "active")
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def check_overlap(
        self, db: AsyncSession, pc_id: int, start_time: datetime, end_time: datetime
    ) -> bool:
        query = select(self.model).where(
            self.model.pc_id == pc_id,
            self.model.status == "active",
            self.model.start_time < end_time,
            self.model.end_time > start_time,
        )
        result = await db.execute(query)
        return result.scalars().first() is not None

    async def cancel_booking(self, db: AsyncSession, booking: Booking) -> Booking:
        booking.status = "cancelled"
        db.add(booking)
        await db.commit()
        await db.refresh(booking)
        return booking

    async def get_active_booking_by_pc(
        self, db: AsyncSession, pc_id: int
    ) -> Booking | None:
        stmt = (
            select(self.model)
            .where(self.model.pc_id == pc_id, self.model.status == "active")
            .order_by(self.model.id.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().first()
