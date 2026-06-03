from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pc import PC
from app.repositories.pc import PCRepository
from app.repositories.zone import ZoneRepository
from app.schemas.pc import PCCreate


class PCService:
    def __init__(self, pc_repo: PCRepository, zone_repo: ZoneRepository) -> None:
        self.pc_repo = pc_repo
        self.zone_repo = zone_repo

    async def create_pc(self, db: AsyncSession, pc_in: PCCreate) -> PC:
        zone = await self.zone_repo.get(db, id=pc_in.zone_id)
        if not zone:
            raise ValueError(f"Zone with ID {pc_in.zone_id} not found")
        return await self.pc_repo.create(db, obj_in=pc_in)

    async def get_pc(self, db: AsyncSession, pc_id: int) -> PC | None:
        pc = await self.pc_repo.get_pc_with_bookings(db, pc_id)
        if not pc:
            return None

        now_shifted = datetime.now(timezone.utc) + timedelta(hours=3)
        pc.status = "available"

        for booking in pc.bookings:
            if (
                booking.start_time <= now_shifted <= booking.end_time
                and booking.status in ["active", "paid", "SUCCESS"]
            ):
                pc.status = "occupied"
                break

        return pc

    async def get_pcs_by_zone(self, db: AsyncSession, zone_id: int) -> Sequence[PC]:
        pcs = await self.pc_repo.get_by_zone(db, zone_id=zone_id)
        now_shifted = datetime.now(timezone.utc) + timedelta(hours=3)

        for pc in pcs:
            pc.status = "available"
            for booking in pc.bookings:
                if (
                    booking.start_time <= now_shifted <= booking.end_time
                    and booking.status == "active"
                ):
                    pc.status = "occupied"
                    break

        return pcs

    async def get_available_pcs(
        self, db: AsyncSession, zone_id: int, start_time: datetime, end_time: datetime
    ) -> Sequence[PC]:
        if start_time >= end_time:
            raise ValueError("Start time must be before end time")

        zone = await self.zone_repo.get(db, id=zone_id)
        if not zone:
            raise ValueError(f"Zone with ID {zone_id} not found")

        return await self.pc_repo.get_available_in_zone(
            db, zone_id=zone_id, start_time=start_time, end_time=end_time
        )
