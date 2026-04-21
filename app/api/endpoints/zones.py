from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.dependencies import get_current_admin_user, get_zone_service
from app.db.database import get_db_session
from app.models.user import User
from app.schemas.zone import ZoneCreate, ZoneResponce
from app.services.zone import ZoneService

router = APIRouter(prefix="/zones", tags=["Zones"])


@router.post("/", response_model=ZoneResponce, status_code=status.HTTP_201_CREATED)
async def create_zone(
    zone_in: ZoneCreate,
    db: AsyncSession = Depends(get_db_session),
    zone_service: ZoneService = Depends(get_zone_service),
    current_user: User = Depends(get_current_admin_user),
):
    return await zone_service.create_zone(db, zone_in=zone_in)


@router.get("/", response_model=list[ZoneResponce])
async def get_zones(
    db: AsyncSession = Depends(get_db_session),
    zone_service: ZoneService = Depends(get_zone_service),
):
    return await zone_service.get_all_zones(db)
