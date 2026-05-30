from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


@pytest.mark.asyncio
async def test_get_available_pcs(async_client: AsyncClient, db: AsyncSession):
    await async_client.post(
        "/api/v1/users/",
        json={"email": "admin_pc@gmail.com", "password": "password123"},
    )
    await db.execute(
        update(User).where(User.email == "admin_pc@gmail.com").values(role="admin", balance=5000.0)
    )
    await db.commit()

    login_resp = await async_client.post(
        "/api/v1/login",
        data={"username": "admin_pc@gmail.com", "password": "password123"},
    )
    admin_headers = {"Authorization": f"Bearer {login_resp.json()['access_token']}"}

    zone_resp = await async_client.post(
        "/api/v1/zones/",
        json={"name": "Available Zone", "hourly_rate": 100.0},
        headers=admin_headers,
    )
    assert zone_resp.status_code == 201
    zone_id = zone_resp.json()["id"]

    pc1_resp = await async_client.post(
        "/api/v1/pcs/",
        json={"mac_address": "11:22:33:44:55:66", "zone_id": zone_id},
        headers=admin_headers,
    )
    pc1_id = pc1_resp.json()["id"]

    pc2_resp = await async_client.post(
        "/api/v1/pcs/",
        json={"mac_address": "AA:BB:CC:DD:EE:FF", "zone_id": zone_id},
        headers=admin_headers,
    )
    pc2_id = pc2_resp.json()["id"]

    now = datetime.now(timezone.utc)
    booked_start = now + timedelta(hours=1)
    booked_end = now + timedelta(hours=3)

    booking_resp = await async_client.post(
        "/api/v1/bookings/",
        json={
            "pc_id": pc1_id,
            "start_time": booked_start.isoformat(),
            "end_time": booked_end.isoformat(),
        },
        headers=admin_headers,
    )
    assert booking_resp.status_code == 201

    search_start_a = now + timedelta(hours=2)
    search_end_a = now + timedelta(hours=4)

    resp_a = await async_client.get(
        "/api/v1/pcs/available",
        params={
            "zone_id": zone_id,
            "start_time": search_start_a.isoformat(),
            "end_time": search_end_a.isoformat(),
        },
    )
    assert resp_a.status_code == 200, f"Error details: {resp_a.json()}"
    data_a = resp_a.json()
    assert len(data_a) == 1
    assert data_a[0]["id"] == pc2_id

    search_start_b = now + timedelta(hours=5)
    search_end_b = now + timedelta(hours=7)

    resp_b = await async_client.get(
        "/api/v1/pcs/available",
        params={
            "zone_id": zone_id,
            "start_time": search_start_b.isoformat(),
            "end_time": search_end_b.isoformat(),
        },
    )
    assert resp_b.status_code == 200, f"Error details: {resp_b.json()}"
    data_b = resp_b.json()
    assert len(data_b) == 2
    available_ids = {pc["id"] for pc in data_b}
    assert available_ids == {pc1_id, pc2_id}
