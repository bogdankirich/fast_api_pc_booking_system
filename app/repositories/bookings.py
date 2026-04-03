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
        self, db: AsyncSession, *, user_id: int
    ) -> Sequence[Booking]:
        query = select(self.model).where(
            self.model.user_id == user_id, self.model.status == "active"
        )
        result = await db.execute(query)
        return result.scalars().all()
