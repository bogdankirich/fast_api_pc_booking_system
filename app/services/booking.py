from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookings import Booking
from app.models.user import User
from app.repositories.booking import BookingRepository
from app.repositories.pc import PCRepository
from app.repositories.zone import ZoneRepository
from app.schemas.booking import BookingCreate


class BookingService:
    def __init__(
        self,
        booking_repo: BookingRepository,
        pc_repo: PCRepository,
        zone_repo: ZoneRepository,
    ):
        self.booking_repo = booking_repo
        self.pc_repo = pc_repo
        self.zone_repo = zone_repo

    async def create_booking(
        self, db: AsyncSession, booking_in: BookingCreate, current_user: User
    ) -> Booking:
        if booking_in.start_time >= booking_in.end_time:
            raise ValueError("End time should be later than start time")

        pc = await self.pc_repo.get(db, id=booking_in.pc_id)
        if not pc:
            raise ValueError("PC not found")

        is_busy = await self.booking_repo.check_overlap(
            db,
            pc_id=booking_in.pc_id,
            start_time=booking_in.start_time,
            end_time=booking_in.end_time,
        )
        if is_busy:
            raise ValueError("This PC is already booked for this time")

        zone = await self.zone_repo.get(db, id=pc.zone_id)
        if not zone:
            raise ValueError("Zone for this PC is not found")

        duration_seconds = (booking_in.end_time - booking_in.start_time).total_seconds()
        duration_hours = Decimal(str(duration_seconds / 3600))

        total_cost = round(duration_hours * zone.hourly_rate, 2)

        booking_data = booking_in.model_dump()
        booking_data["user_id"] = current_user.id
        booking_data["total_cost"] = total_cost
        booking_data["status"] = "active"

        db_obj = Booking(**booking_data)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
