from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.endpoints import auth, bookings, pcs, users, zones
from app.core.config import settings

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
