from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.dependencies import (
    get_admin_user_hybrid,
    get_booking_service,
    get_current_user,
)
from app.db.database import get_db_session
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingResponce
from app.services.booking import BookingService

router = APIRouter(prefix="/bookings", tags=["Bookings"])


# --- СХЕМЫ ДЛЯ АДМИНСКИХ ЗАПРОСОВ ---


class AdminCashBookingRequest(BaseModel):
    pc_id: int
    hours: int


class AdminEndSessionRequest(BaseModel):
    pc_id: int


# --- КЛИЕНТСКИЕ ЭНДПОИНТЫ ---


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
    skip: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db_session),
    booking_service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user),
):
    return await booking_service.booking_repo.get_active_by_user(
        db, user_id=current_user.id, skip=skip, limit=limit
    )


@router.delete("/{booking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_booking(
    booking_id: int,
    db: AsyncSession = Depends(get_db_session),
    booking_service: BookingService = Depends(get_booking_service),
    current_user: User = Depends(get_current_user),
):
    try:
        deleted = await booking_service.cancel_booking(
            db, booking_id=booking_id, current_user=current_user
        )
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Couldn't find booking"
            )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# --- АДМИНСКИЕ ЭНДПОИНТЫ (РУЧНАЯ КАССА) ---


@router.post("/admin/cash-booking", status_code=status.HTTP_201_CREATED)
async def admin_cash_booking(
    payload: AdminCashBookingRequest,
    db: AsyncSession = Depends(get_db_session),
    booking_service: BookingService = Depends(get_booking_service),
    current_admin: User = Depends(get_admin_user_hybrid),
):
    now_utc = datetime.now(timezone.utc)
    end_utc = now_utc + timedelta(hours=payload.hours)

    booking_in = BookingCreate(
        pc_id=payload.pc_id, start_time=now_utc, end_time=end_utc
    )
    try:
        booking = await booking_service.create_cash_booking(db, booking_in=booking_in)
        return {"status": "success", "booking_id": booking.id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/admin/end-session")
async def admin_end_session(
    payload: AdminEndSessionRequest,
    db: AsyncSession = Depends(get_db_session),
    booking_service: BookingService = Depends(get_booking_service),
    current_admin: User = Depends(get_admin_user_hybrid),
):
    try:
        booking = await booking_service.admin_cancel_pc_session(
            db, pc_id=payload.pc_id, admin_user=current_admin
        )
        return {"status": "success", "message": f"Сессия {booking.id} завершена"}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
