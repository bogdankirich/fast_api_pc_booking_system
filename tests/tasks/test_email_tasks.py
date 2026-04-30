from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.bookings import Booking
from app.models.pc import PC
from app.models.user import User
from app.models.zone import Zone
from app.tasks.bookings import _expire_bookings_logic
from tests.conftest import TEST_DATABASE_URL


@pytest.mark.asyncio
async def test_check_expired_bookings_task(db: AsyncSession):

    user = User(email="task_test@gmail.com", hashed_password="123", role="user")
    zone = Zone(name="Task Zone", hourly_rate=100.0)
    db.add_all([user, zone])
    await db.flush()

    pc = PC(mac_address="AA:BB:CC:DD:EE:11", zone_id=zone.id)
    db.add(pc)
    await db.flush()

    now = datetime.now(timezone.utc)

    expired_booking = Booking(
        user_id=user.id,
        pc_id=pc.id,
        start_time=now - timedelta(hours=3),
        end_time=now - timedelta(hours=1),
        total_cost=200.0,
        status="active",
    )

    active_booking = Booking(
        user_id=user.id,
        pc_id=pc.id,
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(hours=2),
        total_cost=300.0,
        status="active",
    )

    db.add_all([expired_booking, active_booking])
    await db.commit()

    def mock_create_engine(*args, **kwargs):

        return create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    with patch(
        "app.tasks.bookings.create_async_engine", side_effect=mock_create_engine
    ):
        await _expire_bookings_logic()

    status_expired = await db.scalar(
        select(Booking.status).where(Booking.id == expired_booking.id)
    )
    status_active = await db.scalar(
        select(Booking.status).where(Booking.id == active_booking.id)
    )

    assert status_expired == "completed"

    assert status_active == "active"
