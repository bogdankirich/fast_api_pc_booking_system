import uuid
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

TEST_DATABASE_URL = (
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:{settings.POSTGRES_PASSWORD}"
    f"@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/test_booking_db"
)

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


# ---------------------------------------------------------------------------
# Вспомогательные функции
# ---------------------------------------------------------------------------


async def create_user_and_login(
    async_client: AsyncClient,
    email: str,
    password: str = "password123",
) -> str:
    """Регистрирует пользователя и возвращает access_token."""
    await async_client.post(
        "/api/v1/users/", json={"email": email, "password": password}
    )
    resp = await async_client.post(
        "/api/v1/login", data={"username": email, "password": password}
    )
    return resp.json()["access_token"]


async def promote_to_admin(db: AsyncSession, email: str) -> None:
    """Назначает роль admin пользователю с указанным email."""
    await db.execute(update(User).where(User.email == email).values(role="admin"))
    await db.commit()


def auth_headers(token: str) -> dict:
    """Формирует заголовок Authorization из токена."""
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Фикстуры пользователей
# ---------------------------------------------------------------------------


@pytest.fixture
async def owner_headers(async_client: AsyncClient) -> dict:
    """Обычный пользователь — владелец бронирования."""
    token = await create_user_and_login(async_client, "owner@gmail.com")
    return auth_headers(token)


@pytest.fixture
async def other_user_headers(async_client: AsyncClient) -> dict:
    """Другой обычный пользователь — для проверки RBAC."""
    token = await create_user_and_login(async_client, "other@gmail.com")
    return auth_headers(token)


@pytest.fixture
async def admin_headers(async_client: AsyncClient, db: AsyncSession) -> dict:
    """Администратор."""
    email = "admin@gmail.com"
    token = await create_user_and_login(async_client, email)
    await promote_to_admin(db, email)
    # Перелогиниваемся, чтобы токен содержал актуальную роль
    token = await create_user_and_login(async_client, email)
    return auth_headers(token)


@pytest.fixture
async def owner_user_id(db: AsyncSession, owner_headers: dict) -> int:
    """ID пользователя owner@gmail.com."""
    from sqlalchemy import select

    result = await db.execute(select(User).where(User.email == "owner@gmail.com"))
    user = result.scalars().first()
    assert user is not None, "User owner@gmail.com must exist"
    return user.id


# ---------------------------------------------------------------------------
# Фикстуры инфраструктуры (через БД)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Фикстура для создания полного окружения бронирования через API
# (используется в тестах, где нужна изоляция по суффиксу)
# ---------------------------------------------------------------------------


async def build_booking_env(
    async_client: AsyncClient,
    db: AsyncSession,
    suffix: str,
    hourly_rate: float = 100.0,
    hours_from_now: tuple[int, int] | None = None,
) -> dict:
    """
    Создаёт изолированное окружение для тестирования бронирований:
    - admin, owner, other — три пользователя с соответствующими ролями
    - zone + pc — инфраструктура
    - бронирование от owner создаётся только если передан hours_from_now

    Возвращает словарь с заголовками, pc_id и опционально booking_id.
    """
    # Admin
    admin_email = f"admin_{suffix}@gmail.com"
    admin_token = await create_user_and_login(async_client, admin_email)
    await promote_to_admin(db, admin_email)
    admin_token = await create_user_and_login(async_client, admin_email)
    admin_hdrs = auth_headers(admin_token)

    # Zone
    zone_resp = await async_client.post(
        "/api/v1/zones/",
        json={"name": f"Zone {suffix}", "hourly_rate": hourly_rate},
        headers=admin_hdrs,
    )
    assert zone_resp.status_code == 201, (
        f"[{suffix}] Zone creation failed: {zone_resp.json()}"
    )
    # PC
    unique_hex = uuid.uuid4().hex
    valid_mac = (
        f"02:00:{unique_hex[0:2]}:{unique_hex[2:4]}:{unique_hex[4:6]}:{unique_hex[6:8]}"
    )

    pc_resp = await async_client.post(
        "/api/v1/pcs/",
        json={
            "mac_address": valid_mac,
            "zone_id": zone_resp.json()["id"],
        },
        headers=admin_hdrs,
    )
    assert pc_resp.status_code == 201, (
        f"[{suffix}] PC creation failed: {pc_resp.json()}"
    )
    pc_id = pc_resp.json()["id"]

    # Owner
    owner_token = await create_user_and_login(async_client, f"owner_{suffix}@gmail.com")
    owner_hdrs = auth_headers(owner_token)

    # Other
    other_token = await create_user_and_login(async_client, f"other_{suffix}@gmail.com")
    other_hdrs = auth_headers(other_token)

    result = {
        "admin_headers": admin_hdrs,
        "owner_headers": owner_hdrs,
        "other_headers": other_hdrs,
        "pc_id": pc_id,
    }

    # Бронирование создаётся только по явному запросу
    if hours_from_now is not None:
        start_h, end_h = hours_from_now
        now = datetime.now(timezone.utc)
        booking_resp = await async_client.post(
            "/api/v1/bookings/",
            json={
                "pc_id": pc_id,
                "start_time": (now + timedelta(hours=start_h)).isoformat(),
                "end_time": (now + timedelta(hours=end_h)).isoformat(),
            },
            headers=owner_hdrs,
        )
        assert booking_resp.status_code == 201, (
            f"[{suffix}] Booking creation failed: {booking_resp.json()}"
        )
        result["booking_id"] = booking_resp.json()["id"]

    return result
