from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_create_booking_success(async_client: AsyncClient, db: AsyncSession):
    await async_client.post(
        "/api/v1/users/", json={"email": "admin@gmail.com", "password": "password123"}
    )

    await db.execute(
        update(User).where(User.email == "admin@gmail.com").values(role="admin")
    )
    await db.commit()

    admin_login = await async_client.post(
        "/api/v1/login", data={"username": "admin@gmail.com", "password": "password123"}
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    zone_response = await async_client.post(
        "/api/v1/zones/",
        json={"name": "VIP Zone", "hourly_rate": 100.0},
        headers=admin_headers,
    )
    assert zone_response.status_code == 201, (
        f"Failed to create zone: {zone_response.json()}"
    )
    zone_id = zone_response.json()["id"]

    pc_response = await async_client.post(
        "/api/v1/pcs/",
        json={
            "mac_address": "00:11:22:33:44:55",
            "zone_id": zone_id,
        },
        headers=admin_headers,
    )
    assert pc_response.status_code == 201, f"Failed to create PC: {pc_response.json()}"
    pc_id = pc_response.json()["id"]

    await async_client.post(
        "/api/v1/users/", json={"email": "gamer@gmail.com", "password": "password123"}
    )

    gamer_login = await async_client.post(
        "/api/v1/login", data={"username": "gamer@gmail.com", "password": "password123"}
    )
    gamer_headers = {"Authorization": f"Bearer {gamer_login.json()['access_token']}"}

    now = datetime.now(timezone.utc)
    start_time = now + timedelta(hours=1)
    end_time = now + timedelta(hours=2)

    booking_response = await async_client.post(
        "/api/v1/bookings/",
        json={
            "pc_id": pc_id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
        },
        headers=gamer_headers,
    )
    assert booking_response.status_code == 201
    data = booking_response.json()
    assert data["pc_id"] == pc_id
    assert data["status"] == "active"
    assert float(data["total_cost"]) == 100.0
