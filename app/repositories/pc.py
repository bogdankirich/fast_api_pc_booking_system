from typing import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
