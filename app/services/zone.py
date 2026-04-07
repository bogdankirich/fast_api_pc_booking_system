from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.zone import Zone
from app.repositories.zone import ZoneRepository
from app.schemas.zone import ZoneCreate


class ZoneService:
    def __init__(self, zone_repo: ZoneRepository):
        self.zone_repo = zone_repo

    async def create_zone(self, db: AsyncSession, zone_in: ZoneCreate) -> Zone:
        return await self.zone_repo.create(db, obj_in=zone_in)

    async def get_all_zones(self, db: AsyncSession) -> Sequence[Zone]:
        return await self.zone_repo.get_multi(db)
