from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db.database import get_db_session
from app.main import app
from app.models.base import Base
from app.models.bookings import Booking
from app.models.pc import PC
from app.models.user import User
from app.models.zone import Zone

TEST_DATABASE_URL = f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/test_booking_db"


test_engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)
test_async_session_maker = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with test_async_session_maker() as session:
        yield session


app.dependency_overrides[get_db_session] = override_get_db_session


@pytest.fixture(autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield
    finally:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.fixture
async def db() -> AsyncGenerator[AsyncSession, None]:
    async with test_async_session_maker() as session:
        yield session


@pytest.fixture
async def owner_headers(async_client: AsyncClient) -> dict:
    """Обычный юзер (владелец бронирования)"""
    email = "owner@gmail.com"
    password = "password123"
    await async_client.post(
        "/api/v1/users/", json={"email": email, "password": password}
    )
    login_resp = await async_client.post(
        "/api/v1/login", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


@pytest.fixture
async def other_user_headers(async_client: AsyncClient) -> dict:
    """Другой обычный юзер (для проверки RBAC)"""
    email = "other@gmail.com"
    password = "password123"
    await async_client.post(
        "/api/v1/users/", json={"email": email, "password": password}
    )
    login_resp = await async_client.post(
        "/api/v1/login", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


@pytest.fixture
async def admin_headers(async_client: AsyncClient, db: AsyncSession) -> dict:
    """Администратор"""
    email = "admin@gmail.com"
    password = "password123"
    await async_client.post(
        "/api/v1/users/", json={"email": email, "password": password}
    )

    # Назначаем роль админа напрямую через БД
    await db.execute(update(User).where(User.email == email).values(role="admin"))
    await db.commit()

    login_resp = await async_client.post(
        "/api/v1/login", data={"username": email, "password": password}
    )
    return {"Authorization": f"Bearer {login_resp.json()['access_token']}"}


@pytest.fixture
async def owner_user_id(db: AsyncSession, owner_headers: dict) -> int:
    """Получаем ID созданного owner-юзера из БД"""
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.email == "owner@gmail.com"))
    user = result.scalars().first()

    assert user is not None, "User owner@gmail.com must exist"

    return user.id


# --- Фикстуры инфраструктуры (через БД) ---


@pytest.fixture
async def test_zone(db: AsyncSession) -> Zone:
    zone = Zone(name="VIP Zone", hourly_rate=100.0)
    db.add(zone)
    await db.commit()
    await db.refresh(zone)
    return zone


@pytest.fixture
async def test_pc(db: AsyncSession, test_zone: Zone) -> PC:
    pc = PC(mac_address="00:11:22:33:44:55", zone_id=test_zone.id)
    db.add(pc)
    await db.commit()
    await db.refresh(pc)
    return pc


@pytest.fixture
async def test_booking(db: AsyncSession, test_pc: PC, owner_user_id: int) -> Booking:
    now = datetime.now(timezone.utc)
    booking = Booking(
        user_id=owner_user_id,
        pc_id=test_pc.id,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=2),
        total_cost=100.0,
        status="active",
    )
    db.add(booking)
    await db.commit()
    await db.refresh(booking)
    return booking
