from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.dependencies import get_current_admin_user, get_pc_service
from app.db.database import get_db_session
from app.models.user import User
from app.schemas.pc import PCCreate, PCResponce
from app.services.pc import PCService

router = APIRouter(prefix="/pcs", tags=["PCs"])


@router.post("/", response_model=PCResponce, status_code=status.HTTP_201_CREATED)
async def create_pc(
    pc_in: PCCreate,
    db: AsyncSession = Depends(get_db_session),
    pc_service: PCService = Depends(get_pc_service),
    current_user: User = Depends(get_current_admin_user),
):
    return await pc_service.create_pc(db, pc_in=pc_in)


@router.get("/available", response_model=list[PCResponce])
async def get_available_pcs(
    zone_id: int = Query(..., description="ID игровой зоны"),
    start_time: datetime = Query(..., description="Начало брони (ISO 8601)"),
    end_time: datetime = Query(..., description="Конец брони (ISO 8601)"),
    db: AsyncSession = Depends(get_db_session),
    pc_service: PCService = Depends(get_pc_service),
):
    try:
        return await pc_service.get_available_pcs(
            db, zone_id=zone_id, start_time=start_time, end_time=end_time
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/zone/{zone_id}", response_model=list[PCResponce])
async def get_pcs_by_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_db_session),
    pc_service: PCService = Depends(get_pc_service),
):
    return await pc_service.get_pcs_by_zone(db, zone_id=zone_id)
