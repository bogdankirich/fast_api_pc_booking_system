from datetime import datetime
from typing import Sequence

from sqlalchemy import and_, exists, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookings import Booking
from app.models.pc import PC
from app.repositories.base import BaseRepository
from app.schemas.pc import PCCreate


class PCRepository(BaseRepository[PC, PCCreate]):
    def __init__(self) -> None:
        super().__init__(PC)

    async def get_by_zone(self, db: AsyncSession, *, zone_id: int) -> Sequence[PC]:
        query = select(self.model).where(self.model.zone_id == zone_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def get_with_lock(self, db: AsyncSession, id: int) -> PC | None:
        query = select(self.model).where(self.model.id == id).with_for_update()
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_available_in_zone(
        self, db: AsyncSession, zone_id: int, start_time: datetime, end_time: datetime
    ) -> Sequence[PC]:
        overlap_condition = exists().where(
            and_(
                Booking.pc_id == self.model.id,
                Booking.status == "active",
                Booking.start_time < end_time,
                Booking.end_time > start_time,
            )
        )

        query = select(self.model).where(
            and_(
                self.model.zone_id == zone_id,
                self.model.status == "available",
                ~overlap_condition,
            )
        )
        result = await db.execute(query)
        return result.scalars().all()
