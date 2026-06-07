from datetime import datetime
from zoneinfo import ZoneInfo

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
        now_local = datetime.now(ZoneInfo("Europe/Kyiv")).replace(tzinfo=None)

        async with async_session_maker() as db:
            result = await db.execute(
                select(PC).options(selectinload(PC.bookings)).order_by(PC.id)
            )
            pcs_db = result.scalars().all()

            pcs_data = []
            for pc in pcs_db:
                status = "available"
                end_time_str = ""
                for b in pc.bookings:
                    start_naive = b.start_time.replace(tzinfo=None)
                    end_naive = b.end_time.replace(tzinfo=None)

                    if start_naive <= now_local <= end_naive and b.status in [
                        "active",
                        "paid",
                        "SUCCESS",
                    ]:
                        status = "occupied"
                        end_time_str = end_naive.isoformat()
                        break

                pcs_data.append(
                    {"id": pc.id, "status": status, "end_time": end_time_str}
                )

        return await self.templates.TemplateResponse(
            request, "admin/live_map.html", context={"pcs": pcs_data}
        )
