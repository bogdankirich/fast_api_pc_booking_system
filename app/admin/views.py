from sqladmin import ModelView

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
