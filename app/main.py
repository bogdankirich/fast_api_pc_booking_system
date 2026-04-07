from fastapi import FastAPI

from app.api.endpoints import auth, pcs, users, zones

app = FastAPI(
    title="Computer Club Booking System API",
    description="Production-ready API for Booking",
    version="1.0.0",
)

app.include_router(users.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(zones.router, prefix="/api/v1")
app.include_router(pcs.router, prefix="/api/v1")
