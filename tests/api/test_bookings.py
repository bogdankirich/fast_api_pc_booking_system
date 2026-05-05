import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.bookings import Booking
from tests.conftest import auth_headers, build_booking_env, create_user_and_login


@pytest.mark.asyncio
async def test_create_booking_success(async_client: AsyncClient, db: AsyncSession):

    env = await build_booking_env(async_client, db, suffix="create")

    now = datetime.now(timezone.utc)
    payload = {
        "pc_id": env["pc_id"],
        "start_time": (now + timedelta(hours=1)).isoformat(),
        "end_time": (now + timedelta(hours=2)).isoformat(),
    }

    create_resp = await async_client.post(
        "/api/v1/bookings/",
        json=payload,
        headers=env["owner_headers"],
    )

    assert create_resp.status_code == 201, f"Booking failed: {create_resp.json()}"

    data = create_resp.json()
    assert data["pc_id"] == env["pc_id"]
    assert data["status"] == "active"

    assert float(data["total_cost"]) == 100.0


@pytest.mark.asyncio
async def test_create_overlapping_booking_fails(
    async_client: AsyncClient, db: AsyncSession
):
    env = await build_booking_env(
        async_client, db, suffix="overlap", hours_from_now=(1, 3)
    )

    gamer2_token = await create_user_and_login(async_client, "gamer2_overlap@gmail.com")

    now = datetime.now(timezone.utc)
    resp2 = await async_client.post(
        "/api/v1/bookings/",
        json={
            "pc_id": env["pc_id"],
            "start_time": (now + timedelta(hours=2)).isoformat(),
            "end_time": (now + timedelta(hours=4)).isoformat(),
        },
        headers=auth_headers(gamer2_token),
    )

    assert resp2.status_code in (400, 409), (
        f"System allowed overlapping booking! Response: {resp2.json()}"
    )


@pytest.mark.asyncio
async def test_create_booking_concurrent_race_condition(
    async_client: AsyncClient, db: AsyncSession
):

    env = await build_booking_env(async_client, db, suffix="race")

    gamer1_token = await create_user_and_login(async_client, "race_gamer1@gmail.com")
    gamer2_token = await create_user_and_login(async_client, "race_gamer2@gmail.com")

    now = datetime.now(timezone.utc)
    payload = {
        "pc_id": env["pc_id"],
        "start_time": (now + timedelta(hours=1)).isoformat(),
        "end_time": (now + timedelta(hours=3)).isoformat(),
    }

    response1, response2 = await asyncio.gather(
        async_client.post(
            "/api/v1/bookings/", json=payload, headers=auth_headers(gamer1_token)
        ),
        async_client.post(
            "/api/v1/bookings/", json=payload, headers=auth_headers(gamer2_token)
        ),
    )

    statuses = [response1.status_code, response2.status_code]

    assert 201 in statuses or 200 in statuses, (
        f"Expected one success, got: {statuses}.\n"
        f"Resp1: {response1.text}\nResp2: {response2.text}"
    )

    assert 400 in statuses or 409 in statuses, (
        f"Expected one failure (blocked by lock), got: {statuses}.\n"
        f"Resp1: {response1.text}\nResp2: {response2.text}"
    )


@pytest.mark.asyncio
async def test_cancel_booking_by_owner_success(
    async_client: AsyncClient,
    db: AsyncSession,
    owner_headers: dict,
    test_booking: Booking,
):
    response = await async_client.delete(
        f"/api/v1/bookings/{test_booking.id}", headers=owner_headers
    )
    assert response.status_code == 204

    await db.refresh(test_booking)
    assert test_booking.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_booking_by_admin_success(
    async_client: AsyncClient,
    db: AsyncSession,
    admin_headers: dict,
    test_booking: Booking,
):
    response = await async_client.delete(
        f"/api/v1/bookings/{test_booking.id}", headers=admin_headers
    )
    assert response.status_code == 204

    await db.refresh(test_booking)
    assert test_booking.status == "cancelled"


@pytest.mark.asyncio
async def test_cancel_booking_rbac_forbidden(
    async_client: AsyncClient,
    db: AsyncSession,
    other_user_headers: dict,
    test_booking: Booking,
):
    response = await async_client.delete(
        f"/api/v1/bookings/{test_booking.id}", headers=other_user_headers
    )
    assert response.status_code == 403
    assert "you do not have the right to cancel" in response.json()["detail"].lower()

    booking_in_db = (
        (await db.execute(select(Booking).where(Booking.id == test_booking.id)))
        .scalars()
        .first()
    )
    assert booking_in_db is not None
    assert booking_in_db.status == "active"


@pytest.mark.asyncio
async def test_cancel_booking_not_found(async_client: AsyncClient, owner_headers: dict):
    response = await async_client.delete(
        "/api/v1/bookings/999999", headers=owner_headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_cancel_booking_idempotency(
    async_client: AsyncClient,
    db: AsyncSession,
    owner_headers: dict,
    test_booking: Booking,
):
    resp1 = await async_client.delete(
        f"/api/v1/bookings/{test_booking.id}", headers=owner_headers
    )
    assert resp1.status_code == 204

    resp2 = await async_client.delete(
        f"/api/v1/bookings/{test_booking.id}", headers=owner_headers
    )
    assert resp2.status_code == 204
