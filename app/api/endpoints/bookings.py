from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.dependencies import get_booking_service, get_current_user
from app.db.database import get_db_session
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingResponce
from app.services.booking import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


@router.post("/", response_model=BookingResponce, status_code=status.HTTP_201_CREATED)
async def create_booking(
    booking_in: BookingCreate,
    db: AsyncSession = Depends(get_db_session),
    booking_service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user),
):
    try:
        return await booking_service.create_booking(
            db, booking_in=booking_in, current_user=current_user
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=list[BookingResponce])
async def get_my_bookings(
    db: AsyncSession = Depends(get_db_session),
    booking_service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user),
):
    return await booking_service.booking_repo.get_active_by_user(
        db, user_id=current_user.id
    )
