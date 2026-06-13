"""
Тесты для административных функций бронирования:
- POST /bookings/admin/cash-booking — ручная касса
- POST /bookings/admin/end-session — досрочное завершение сессии
- Гибридная авторизация (JWT + Session)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.bookings import Booking
from app.models.user import User
from tests.conftest import build_booking_env, create_user_and_login

# ============================================================================
# ТЕСТЫ ЭНДПОИНТА: POST /bookings/admin/cash-booking
# ============================================================================


@pytest.mark.smoke
@pytest.mark.integration
async def test_admin_cash_booking_success(async_client: AsyncClient, db: AsyncSession):
    """Success: Администратор создает бронь через кассу на текущее время + N часов."""
    env = await build_booking_env(async_client, db, suffix="cash_success")

    payload = {"pc_id": env["pc_id"], "hours": 2}

    response = await async_client.post(
        "/api/v1/bookings/admin/cash-booking",
        json=payload,
        headers=env["admin_headers"],
    )

    assert response.status_code == 201, f"Cash booking failed: {response.json()}"
    data = response.json()
    assert data["status"] == "success"
    assert "booking_id" in data

    # Проверяем, что бронь действительно создана в БД
    booking_id = data["booking_id"]
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalars().first()

    assert booking is not None
    assert booking.pc_id == env["pc_id"]
    assert booking.status == "active"

    # Проверяем, что бронь создана на текущее время (UTC) + 2 часа
    now_utc = datetime.now(timezone.utc)
    time_diff_start = abs((booking.start_time - now_utc).total_seconds())
    time_diff_end = abs(
        (booking.end_time - (now_utc + timedelta(hours=2))).total_seconds()
    )

    # Допускаем погрешность в 5 секунд
    assert time_diff_start < 5, (
        f"Start time mismatch: {booking.start_time} vs {now_utc}"
    )
    assert time_diff_end < 5, (
        f"End time mismatch: {booking.end_time} vs {now_utc + timedelta(hours=2)}"
    )


@pytest.mark.integration
async def test_admin_cash_booking_unauthorized_guest(
    async_client: AsyncClient, db: AsyncSession
):
    """Fail (401): Попытка создать бронь без заголовка авторизации."""
    env = await build_booking_env(async_client, db, suffix="cash_unauth")

    payload = {"pc_id": env["pc_id"], "hours": 1}

    response = await async_client.post(
        "/api/v1/bookings/admin/cash-booking",
        json=payload,
        # НЕ передаем headers
    )

    assert response.status_code == 401, (
        f"Expected 401, got {response.status_code}: {response.json()}"
    )


@pytest.mark.integration
async def test_admin_cash_booking_forbidden_regular_user(
    async_client: AsyncClient, db: AsyncSession
):
    """Fail (401/403): Обычный пользователь не может создать бронь через кассу."""
    env = await build_booking_env(async_client, db, suffix="cash_forbidden")

    payload = {"pc_id": env["pc_id"], "hours": 1}

    # owner_headers принадлежит обычному пользователю (не админу)
    response = await async_client.post(
        "/api/v1/bookings/admin/cash-booking",
        json=payload,
        headers=env["owner_headers"],
    )

    # Зависимость должна выбросить 401 (нет admin роли)
    assert response.status_code in (401, 403), (
        f"Regular user should not access cash booking: {response.json()}"
    )


@pytest.mark.integration
async def test_admin_cash_booking_overlap_fails(
    async_client: AsyncClient, db: AsyncSession
):
    """Fail (400): Попытка забронировать ПК, который уже занят (active бронь)."""
    # Создаем окружение с активной бронью на текущее время + 1-3 часа
    env = await build_booking_env(
        async_client, db, suffix="cash_overlap", hours_from_now=(0, 3)
    )

    # Пытаемся создать новую бронь через кассу на текущее время + 2 часа (оверлап)
    payload = {"pc_id": env["pc_id"], "hours": 2}

    response = await async_client.post(
        "/api/v1/bookings/admin/cash-booking",
        json=payload,
        headers=env["admin_headers"],
    )

    assert response.status_code == 400, f"Expected overlap error: {response.json()}"
    assert "забронирован" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_admin_cash_booking_after_cancelled_slot_success(
    async_client: AsyncClient, db: AsyncSession
):
    """Success: Создание брони успешно, если в слоте есть старая бронь со статусом cancelled."""
    env = await build_booking_env(
        async_client, db, suffix="cash_cancelled", hours_from_now=(0, 2)
    )

    # Отменяем существующую бронь
    booking_id = env["booking_id"]
    cancel_resp = await async_client.delete(
        f"/api/v1/bookings/{booking_id}",
        headers=env["admin_headers"],
    )
    assert cancel_resp.status_code == 204

    # Проверяем, что бронь действительно отменена
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    cancelled_booking = result.scalars().first()
    assert cancelled_booking is not None, "Booking must exist in database"
    assert cancelled_booking.status == "cancelled"

    # Теперь создаем новую бронь через кассу на тот же слот
    payload = {"pc_id": env["pc_id"], "hours": 2}

    response = await async_client.post(
        "/api/v1/bookings/admin/cash-booking",
        json=payload,
        headers=env["admin_headers"],
    )

    assert response.status_code == 201, (
        f"Should allow booking in cancelled slot: {response.json()}"
    )


# ============================================================================
# ТЕСТЫ ЭНДПОИНТА: POST /bookings/admin/end-session
# ============================================================================


@pytest.mark.smoke
@pytest.mark.integration
async def test_admin_end_session_success(async_client: AsyncClient, db: AsyncSession):
    """Success: Администратор завершает активную сессию по pc_id."""
    env = await build_booking_env(
        async_client, db, suffix="end_success", hours_from_now=(0, 2)
    )

    payload = {"pc_id": env["pc_id"]}

    response = await async_client.post(
        "/api/v1/bookings/admin/end-session",
        json=payload,
        headers=env["admin_headers"],
    )

    assert response.status_code == 200, f"End session failed: {response.json()}"
    data = response.json()
    assert data["status"] == "success"
    assert "завершена" in data["message"].lower()

    # Проверяем, что бронь действительно отменена в БД
    booking_id = env["booking_id"]
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalars().first()

    assert booking is not None
    assert booking.status == "cancelled"


@pytest.mark.integration
async def test_admin_end_session_not_found(async_client: AsyncClient, db: AsyncSession):
    """Fail (404): Попытка завершить сессию на ПК, где нет активной брони."""
    env = await build_booking_env(async_client, db, suffix="end_notfound")
    # НЕ создаем бронь (hours_from_now не передан)

    payload = {"pc_id": env["pc_id"]}

    response = await async_client.post(
        "/api/v1/bookings/admin/end-session",
        json=payload,
        headers=env["admin_headers"],
    )

    assert response.status_code == 404, (
        f"Expected 404, got {response.status_code}: {response.json()}"
    )
    assert "не найдена" in response.json()["detail"].lower()


@pytest.mark.integration
async def test_admin_end_session_unauthorized(
    async_client: AsyncClient, db: AsyncSession
):
    """Fail (401): Попытка завершить сессию без авторизации."""
    env = await build_booking_env(
        async_client, db, suffix="end_unauth", hours_from_now=(0, 2)
    )

    payload = {"pc_id": env["pc_id"]}

    response = await async_client.post(
        "/api/v1/bookings/admin/end-session",
        json=payload,
        # НЕ передаем headers
    )

    assert response.status_code == 401


@pytest.mark.integration
async def test_admin_end_session_forbidden_regular_user(
    async_client: AsyncClient, db: AsyncSession
):
    """Fail (401/403): Обычный пользователь не может завершить сессию."""
    env = await build_booking_env(
        async_client, db, suffix="end_forbidden", hours_from_now=(0, 2)
    )

    payload = {"pc_id": env["pc_id"]}

    response = await async_client.post(
        "/api/v1/bookings/admin/end-session",
        json=payload,
        headers=env["owner_headers"],  # обычный пользователь
    )

    assert response.status_code in (401, 403)


# ============================================================================
# ТЕСТЫ ЛОГИКИ ОВЕРЛАПА В BookingService
# ============================================================================


@pytest.mark.integration
async def test_booking_overlap_logic_cancelled_slot_allows(
    async_client: AsyncClient, db: AsyncSession
):
    """Success: Логика оверлапа разрешает создание брони, если в слоте только cancelled брони."""
    env = await build_booking_env(
        async_client, db, suffix="overlap_cancelled", hours_from_now=(1, 3)
    )

    # Отменяем существующую бронь
    cancel_resp = await async_client.delete(
        f"/api/v1/bookings/{env['booking_id']}",
        headers=env["admin_headers"],
    )
    assert cancel_resp.status_code == 204

    # Создаем новую бронь на тот же слот от другого пользователя
    now = datetime.now(timezone.utc)
    response = await async_client.post(
        "/api/v1/bookings/",
        json={
            "pc_id": env["pc_id"],
            "start_time": (now + timedelta(hours=1)).isoformat(),
            "end_time": (now + timedelta(hours=3)).isoformat(),
        },
        headers=env["other_headers"],
    )

    assert response.status_code == 201, (
        f"Should allow booking after cancelled: {response.json()}"
    )


@pytest.mark.integration
async def test_booking_overlap_logic_active_slot_rejects(
    async_client: AsyncClient, db: AsyncSession
):
    """Fail: Логика оверлапа отклоняет создание брони, если в слоте есть active бронь."""
    env = await build_booking_env(
        async_client, db, suffix="overlap_active", hours_from_now=(1, 3)
    )

    # Пытаемся создать новую бронь на пересекающийся слот
    now = datetime.now(timezone.utc)
    response = await async_client.post(
        "/api/v1/bookings/",
        json={
            "pc_id": env["pc_id"],
            "start_time": (now + timedelta(hours=2)).isoformat(),
            "end_time": (now + timedelta(hours=4)).isoformat(),
        },
        headers=env["other_headers"],
    )

    assert response.status_code == 400, (
        f"Should reject overlapping booking: {response.json()}"
    )
    assert "already booked" in response.json()["detail"].lower()


# ============================================================================
# UNIT-ТЕСТЫ ЗАВИСИМОСТИ: get_admin_user_hybrid
# ============================================================================


@pytest.mark.unit
async def test_hybrid_auth_session_success(async_client: AsyncClient, db: AsyncSession):
    """Success (Session): Авторизация через request.session (sqladmin cookie)."""
    # Создаем админа
    admin_email = "admin_session@test.com"
    await async_client.post(
        "/api/v1/users/", json={"email": admin_email, "password": "password123"}
    )

    # Повышаем до админа
    await db.execute(update(User).where(User.email == admin_email).values(role="admin"))
    await db.commit()

    # Получаем ID админа
    result = await db.execute(select(User).where(User.email == admin_email))
    admin_user = result.scalars().first()
    assert admin_user is not None

    # Имитируем session-based auth (как в sqladmin)
    # Для этого нужно использовать тестовый endpoint, который вызывает зависимость
    # Но для unit-теста лучше протестировать зависимость напрямую

    from fastapi import Request

    from app.api.dependencies.dependencies import get_admin_user_hybrid
    from app.repositories.user import UserRepository
    from app.services.user import UserService

    # Создаем mock Request с session
    mock_request = MagicMock(spec=Request)
    mock_request.session = {"token": str(admin_user.id)}

    user_service = UserService(UserRepository())

    # Вызываем зависимость напрямую
    result_user = await get_admin_user_hybrid(
        request=mock_request,
        db=db,
        token=None,  # type: ignore
        user_service=user_service,
    )

    assert result_user.id == admin_user.id
    assert result_user.role == "admin"


@pytest.mark.unit
async def test_hybrid_auth_jwt_success(async_client: AsyncClient, db: AsyncSession):
    """Success (JWT): Авторизация через JWT токен в заголовке Authorization."""
    # Создаем админа
    admin_email = "admin_jwt@test.com"
    token = await create_user_and_login(async_client, admin_email)

    # Повышаем до админа
    await db.execute(update(User).where(User.email == admin_email).values(role="admin"))
    await db.commit()

    # Генерируем новый JWT с обновленной ролью
    result = await db.execute(select(User).where(User.email == admin_email))
    admin_user = result.scalars().first()

    assert admin_user is not None, "User should be in database"

    jwt_token = jwt.encode(
        {"sub": admin_user.email}, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    from fastapi import Request

    from app.api.dependencies.dependencies import get_admin_user_hybrid
    from app.repositories.user import UserRepository
    from app.services.user import UserService

    # Mock Request без session
    mock_request = MagicMock(spec=Request)
    mock_request.session = {}

    user_service = UserService(UserRepository())

    # Вызываем зависимость с JWT токеном
    result_user = await get_admin_user_hybrid(
        request=mock_request,
        db=db,
        token=jwt_token,
        user_service=user_service,
    )

    assert result_user.id == admin_user.id
    assert result_user.role == "admin"


@pytest.mark.unit
async def test_hybrid_auth_no_credentials_fail(db: AsyncSession):
    """Fail (401): Отсутствие и session, и JWT токена."""
    from fastapi import HTTPException, Request

    from app.api.dependencies.dependencies import get_admin_user_hybrid
    from app.repositories.user import UserRepository
    from app.services.user import UserService

    mock_request = MagicMock(spec=Request)
    mock_request.session = {}

    user_service = UserService(UserRepository())

    with pytest.raises(HTTPException) as exc_info:
        await get_admin_user_hybrid(
            request=mock_request,
            db=db,
            token=None,  # type: ignore
            user_service=user_service,
        )

    assert exc_info.value.status_code == 401
    assert "не авторизован" in exc_info.value.detail.lower()


@pytest.mark.unit
async def test_hybrid_auth_wrong_role_fail(async_client: AsyncClient, db: AsyncSession):
    """Fail (401): Пользователь авторизован, но роль не admin."""
    # Создаем обычного пользователя (не админа)
    user_email = "user_no_admin@test.com"
    await async_client.post(
        "/api/v1/users/", json={"email": user_email, "password": "password123"}
    )

    result = await db.execute(select(User).where(User.email == user_email))
    regular_user = result.scalars().first()
    assert regular_user is not None, "Regular user should be created"
    assert regular_user.role != "admin"

    from fastapi import HTTPException, Request

    from app.api.dependencies.dependencies import get_admin_user_hybrid
    from app.repositories.user import UserRepository
    from app.services.user import UserService

    mock_request = MagicMock(spec=Request)
    mock_request.session = {"token": str(regular_user.id)}

    user_service = UserService(UserRepository())

    with pytest.raises(HTTPException) as exc_info:
        await get_admin_user_hybrid(
            request=mock_request,
            db=db,
            token=None,  # type:ignore
            user_service=user_service,
        )

    assert exc_info.value.status_code == 401
