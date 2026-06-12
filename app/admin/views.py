from datetime import datetime, timezone

from sqladmin import BaseView, ModelView, expose
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from starlette.requests import Request

from app.db.database import async_session_maker
from app.models.bookings import Booking
from app.models.pc import PC
from app.models.user import User


class UserAdmin(ModelView, model=User):
    column_list = [User.id, User.email, User.telegram_id, User.role]
    column_searchable_list = [User.email, User.telegram_id]
    column_sortable_list = [User.id]
    icon = "fa-solid fa-user"


class PCAdmin(ModelView, model=PC):
    name = "PC"
    name_plural = "PCs"
    column_list = [PC.id, PC.mac_address, PC.zone_id, PC.status]
    column_searchable_list = [PC.mac_address]
    icon = "fa-solid fa-desktop"


class BookingAdmin(ModelView, model=Booking):
    column_list = [
        Booking.id,
        Booking.user_id,
        Booking.pc_id,
        Booking.start_time,
        Booking.end_time,
        Booking.status,
    ]
    column_sortable_list = [Booking.start_time]
    icon = "fa-solid fa-calendar-check"


class LiveMapView(BaseView):
    name = "Live Map"
    icon = "fa-solid fa-map-location-dot"

    @expose("/live-map", methods=["GET"])
    async def live_map_page(self, request: Request):
        # Используем чистое UTC, так как в базе теперь всё в UTC!
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        async with async_session_maker() as db:
            result = await db.execute(
                select(PC).options(selectinload(PC.bookings)).order_by(PC.id)
            )
            pcs_db = result.scalars().all()

            pcs_data = []
            for pc in pcs_db:
                status = "available"
                end_time_str = ""
                next_booking_time = ""  # <-- Новая переменная для будущей брони

                for b in pc.bookings:
                    # Игнорируем отмененные
                    if b.status not in ["active", "paid", "SUCCESS"]:
                        continue

                    start_naive = b.start_time.replace(tzinfo=None)
                    end_naive = b.end_time.replace(tzinfo=None)

                    # 1. Если кто-то играет ПРЯМО СЕЙЧАС
                    if start_naive <= now_utc <= end_naive:
                        status = "occupied"
                        # Переводим UTC в ISO, чтобы таймер в JS отработал правильно
                        end_time_str = b.end_time.isoformat()

                    # 2. Если бронь В БУДУЩЕМ (комп сейчас свободен)
                    elif start_naive > now_utc:
                        # Запоминаем время начала (форматируем для админа)
                        # Можно перевести в локальное время для вывода, но для простоты отдадим ISO
                        next_booking_time = b.start_time.isoformat()

                pcs_data.append(
                    {
                        "id": pc.id,
                        "status": status,
                        "end_time": end_time_str,
                        "next_booking": next_booking_time,  # <-- Прокидываем в шаблон
                    }
                )

        return await self.templates.TemplateResponse(
            request, "admin/live_map.html", context={"pcs": pcs_data}
        )
