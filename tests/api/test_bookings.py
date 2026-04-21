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


@pytest.mark.asyncio
async def test_create_overlapping_booking_fails(
    async_client: AsyncClient, db: AsyncSession
):
    admin_reg = await async_client.post(
        "/api/v1/users/", json={"email": "admin2@gmail.com", "password": "password123"}
    )

    assert admin_reg.status_code == 201, f"Admin reg failed: {admin_reg.json()}"

    await db.execute(
        update(User).where(User.email == "admin2@gmail.com").values(role="admin")
    )

    await db.commit()

    admin_login = await async_client.post(
        "/api/v1/login",
        data={"username": "admin2@gmail.com", "password": "password123"},
    )
    assert admin_login.status_code == 200, f"Admin login failed: {admin_login.json()}"
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    zone_resp = await async_client.post(
        "/api/v1/zones/",
        json={"name": "Overlap Zone", "hourly_rate": 100.0},
        headers=admin_headers,
    )
    assert zone_resp.status_code == 201, f"Zone failed: {zone_resp.json()}"
    zone_id = zone_resp.json()["id"]

    pc_resp = await async_client.post(
        "/api/v1/pcs/",
        json={"name": "Overlap-PC", "mac_address": "AA:BB", "zone_id": zone_id},
        headers=admin_headers,
    )
    assert pc_resp.status_code == 201, f"PC failed: {pc_resp.json()}"
    pc_id = pc_resp.json()["id"]

    await async_client.post(
        "/api/v1/users/", json={"email": "gamer1@gmail.com", "password": "password123"}
    )
    await async_client.post(
        "/api/v1/users/", json={"email": "gamer2@gmail.com", "password": "password123"}
    )

    token1 = (
        await async_client.post(
            "/api/v1/login",
            data={"username": "gamer1@gmail.com", "password": "password123"},
        )
    ).json()["access_token"]
    token2 = (
        await async_client.post(
            "/api/v1/login",
            data={"username": "gamer2@gmail.com", "password": "password123"},
        )
    ).json()["access_token"]

    now = datetime.now(timezone.utc)
    start_time_1 = now + timedelta(hours=1)
    end_time_1 = now + timedelta(hours=3)

    resp1 = await async_client.post(
        "/api/v1/bookings/",
        json={
            "pc_id": pc_id,
            "start_time": start_time_1.isoformat(),
            "end_time": end_time_1.isoformat(),
        },
        headers={"Authorization": f"Bearer {token1}"},
    )
    assert resp1.status_code == 201

    start_time_2 = now + timedelta(hours=2)
    end_time_2 = now + timedelta(hours=4)

    resp2 = await async_client.post(
        "/api/v1/bookings/",
        json={
            "pc_id": pc_id,
            "start_time": start_time_2.isoformat(),
            "end_time": end_time_2.isoformat(),
        },
        headers={"Authorization": f"Bearer {token2}"},
    )

    assert resp2.status_code in (400, 409), (
        f"System allowed overlapping booking! Response: {resp2.json()}"
    )
