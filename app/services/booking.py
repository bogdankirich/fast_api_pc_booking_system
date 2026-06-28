from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.websockets import manager
from app.models.bookings import Booking
from app.models.transactions import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.repositories.booking import BookingRepository
from app.repositories.pc import PCRepository
from app.repositories.user import UserRepository
from app.repositories.zone import ZoneRepository
from app.schemas.booking import BookingCreate
from app.services.user import UserService
from app.tasks.email import send_receipt
from app.tasks.telegram_notifications import send_booking_reminder


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

        pc = await self.pc_repo.get_with_lock(db, id=booking_in.pc_id)
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

        if current_user.balance < total_cost:
            raise ValueError(
                f"Недостаточно средств. Стоимость: {total_cost} ₴, ваш баланс: {current_user.balance} ₴."
            )

        current_user.balance -= total_cost

        booking_data = booking_in.model_dump()
        booking_data["user_id"] = current_user.id
        booking_data["total_cost"] = total_cost
        booking_data["status"] = "active"

        db_obj = Booking(**booking_data)
        db.add(db_obj)

        withdrawal_tx = Transaction(
            user_id=current_user.id,
            amount=total_cost,
            status=TransactionStatus.SUCCESS,
            type=TransactionType.WITHDRAWAL,
        )
        db.add(withdrawal_tx)

        await db.commit()
        await db.refresh(db_obj)

        send_receipt.delay(
            user_email=current_user.email,
            pc_id=db_obj.pc_id,
            start_time=db_obj.start_time.isoformat(),
            end_time=db_obj.end_time.isoformat(),
            total_cost=str(db_obj.total_cost),
        )

        if current_user.telegram_id:
            # 1. Берем текущее время строго в UTC
            now_utc = datetime.now(timezone.utc)

            # 2. Берем время конца брони. Если SQLAlchemy отдает его без зоны (naive),
            # мы явно говорим, что это UTC, чтобы питон мог их вычесть.
            end_time_utc = db_obj.end_time
            if end_time_utc.tzinfo is None:
                end_time_utc = end_time_utc.replace(tzinfo=timezone.utc)

            # 3. Считаем реальную разницу в секундах
            seconds_until_end = (end_time_utc - now_utc).total_seconds()
            countdown_seconds = int(seconds_until_end - (15 * 60))

            # 4. Если до конца сеанса больше 15 минут — планируем задачу
            if countdown_seconds > 0:
                # Для текста в Телеграме переводим UTC обратно в Киев!
                kiev_tz = ZoneInfo("Europe/Kyiv")
                end_time_str = end_time_utc.astimezone(kiev_tz).strftime("%H:%M")

                send_booking_reminder.apply_async(  # type: ignore
                    kwargs={
                        "booking_id": db_obj.id,
                        "telegram_id": current_user.telegram_id,
                        "pc_number": db_obj.pc_id,
                        "end_time_str": end_time_str,
                    },
                    countdown=countdown_seconds,
                )
        now_utc = datetime.now(timezone.utc)

        start_time_utc = db_obj.start_time
        if start_time_utc.tzinfo is None:
            start_time_utc = start_time_utc.replace(tzinfo=timezone.utc)

        end_time_utc = db_obj.end_time
        if end_time_utc.tzinfo is None:
            end_time_utc = end_time_utc.replace(tzinfo=timezone.utc)

        # Обновляем карту в реальном времени, ТОЛЬКО если сеанс начался
        if start_time_utc <= now_utc <= end_time_utc:
            # Для фронтенда оставляем формат, который он ожидает (наивный ISO)
            end_time_iso = db_obj.end_time.replace(tzinfo=None).isoformat()
            await manager.broadcast_pc_update(
                pc_id=db_obj.pc_id, status="occupied", end_time=end_time_iso
            )

        return db_obj

    async def cancel_booking(
        self, db: AsyncSession, booking_id: int, current_user: User
    ) -> bool:
        booking = await self.booking_repo.get(db, id=booking_id)
        if not booking:
            return False
        if booking.user_id != current_user.id and current_user.role != "admin":
            raise PermissionError("You do not have the right to cancel this booking")
        if booking.status == "cancelled":
            return True

        await self.booking_repo.cancel_booking(db, booking)
        await manager.broadcast_pc_update(
            pc_id=booking.pc_id, status="available", end_time=""
        )
        return True

    async def create_cash_booking(
        self, db: AsyncSession, booking_in: BookingCreate
    ) -> Booking:

        if booking_in.start_time >= booking_in.end_time:
            raise ValueError("Конечное время должно быть позже начального")

        pc = await self.pc_repo.get_with_lock(db, id=booking_in.pc_id)
        if not pc:
            raise ValueError("Компьютер не найден")

        is_busy = await self.booking_repo.check_overlap(
            db,
            pc_id=booking_in.pc_id,
            start_time=booking_in.start_time,
            end_time=booking_in.end_time,
        )
        if is_busy:
            raise ValueError("Этот ПК уже забронирован на выбранное время")

        zone = await self.zone_repo.get(db, id=pc.zone_id)
        if not zone:
            raise ValueError("Зона для этого ПК не найдена")

        duration_seconds = (booking_in.end_time - booking_in.start_time).total_seconds()
        duration_hours = Decimal(str(duration_seconds / 3600))
        total_cost = round(duration_hours * zone.hourly_rate, 2)

        user_service = UserService(UserRepository())
        guest_user = await user_service.get_or_create_guest_user(db)

        booking_data = booking_in.model_dump()
        booking_data["user_id"] = guest_user.id
        booking_data["total_cost"] = total_cost
        booking_data["status"] = "active"

        db_obj = Booking(**booking_data)
        db.add(db_obj)

        cash_tx = Transaction(
            user_id=guest_user.id,
            amount=total_cost,
            status=TransactionStatus.SUCCESS,
            type=TransactionType.CASH,
        )

        db.add(cash_tx)
        await db.commit()
        await db.refresh(db_obj)

        end_time_iso = db_obj.end_time.isoformat()

        await manager.broadcast_pc_update(
            pc_id=db_obj.pc_id, status="occupied", end_time=end_time_iso
        )

        return db_obj

    async def admin_cancel_pc_session(
        self, db: AsyncSession, pc_id: int, admin_user: User
    ):

        active_booking = await self.booking_repo.get_active_booking_by_pc(db, pc_id)

        if not active_booking:
            raise ValueError(f"Активная сессия для ПК {pc_id} не найдена")

        await self.cancel_booking(
            db, booking_id=active_booking.id, current_user=admin_user
        )

        return active_booking
