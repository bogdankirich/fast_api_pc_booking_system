from fastapi import FastAPI

from app.api.endpoints import users

app = FastAPI(
    title="Computer Club Booking System API",
    description="Production-ready API for Booking",
    version="1.0.0",
)

app.include_router(users.router, prefix="/api/v1")
