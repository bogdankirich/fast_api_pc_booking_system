from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.dependencies import get_current_admin_user, get_pc_service
from app.db.database import get_db_session
from app.models.user import User
from app.schemas.pc import PCCreate, PCResponce
from app.services.pc import PCService

router = APIRouter(prefix="/pcs", tags=["PCs"])


@router.post("/", response_model=PCResponce)
async def create_pc(
    pc_in: PCCreate,
    db: AsyncSession = Depends(get_db_session),
    pc_service: PCService = Depends(get_pc_service),
    current_user: User = Depends(get_current_admin_user),
):
    return await pc_service.create_pc(db, pc_in=pc_in)


@router.get("/zone/{zone_id}", response_model=list[PCResponce])
async def get_pcs_by_zone(
    zone_id: int,
    db: AsyncSession = Depends(get_db_session),
    pc_service: PCService = Depends(get_pc_service),
):
    return await pc_service.get_pcs_by_zone(db, zone_id=zone_id)
