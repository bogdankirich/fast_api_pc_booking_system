from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqladmin import Admin
from starlette.middleware.sessions import SessionMiddleware

from app.admin.auth_admin import AdminAuth
from app.admin.views import BookingAdmin, PCAdmin, UserAdmin
from app.api.endpoints import auth, bookings, pcs, users, zones
from app.core.config import settings
from app.db.database import engine

app = FastAPI(
    title="Computer Club Booking System API",
    description="Production-ready API for Booking",
    version="1.0.0",
)

app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.add_middleware(
    CORSMiddleware,
    allow_origins="*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(zones.router, prefix="/api/v1")
app.include_router(pcs.router, prefix="/api/v1")
app.include_router(bookings.router, prefix="/api/v1")

authentication_backend = AdminAuth(secret_key=settings.SECRET_KEY)

admin = Admin(app=app, engine=engine, authentication_backend=authentication_backend)

admin.add_view(UserAdmin)
admin.add_view(PCAdmin)
admin.add_view(BookingAdmin)
