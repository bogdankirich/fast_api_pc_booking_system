from app.models.zone import Zone
from app.repositories.base import BaseRepository
from app.schemas.zone import ZoneCreate


class ZoneRepository(BaseRepository[Zone, ZoneCreate]):
    def __init__(self) -> None:
        super().__init__(Zone)
