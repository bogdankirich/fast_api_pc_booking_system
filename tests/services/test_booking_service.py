"""
Unit-тесты для BookingService.

Фокус на изолированном тестировании бизнес-логики:
- Проверки баланса пользователя
- Расчеты стоимости бронирования
- Валидация времени (прошлое, будущее, overlap)
- Изменение статусов бронирования
- Edge cases (PC не найден, зона не найдена)

Все внешние зависимости (repos, websockets, celery) замокированы.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.bookings import Booking
from app.models.pc import PC
from app.models.user import User
from app.models.zone import Zone
from app.schemas.booking import BookingCreate
from app.services.booking import BookingService


# ============================================================================
# ФИКСТУРЫ
# ============================================================================


@pytest.fixture
def mock_booking_repo():
    """Mock репозитория бронирований."""
    return AsyncMock()


@pytest.fixture
def mock_pc_repo():
    """Mock репозитория ПК."""
    return AsyncMock()


@pytest.fixture
def mock_zone_repo():
    """Mock репозитория зон."""
    return AsyncMock()


@pytest.fixture
def booking_service(mock_booking_repo, mock_pc_repo, mock_zone_repo):
    """Экземпляр BookingService с замоканными зависимостями."""
    return BookingService(
        booking_repo=mock_booking_repo,
        pc_repo=mock_pc_repo,
        zone_repo=mock_zone_repo,
    )


@pytest.fixture
def mock_db():
    """Mock асинхронной сессии БД."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def sample_user():
    """Пользователь с балансом 1000₴."""
    user = User(
        id=1,
        email="user@test.com",
        hashed_password="hashed",
        balance=Decimal("1000.00"),
        role="user",
        telegram_id=None,
    )
    return user


@pytest.fixture
def sample_pc():
    """Тестовый ПК."""
    return PC(id=1, mac_address="00:11:22:33:44:55", zone_id=1)


@pytest.fixture
def sample_zone():
    """Зона со ставкой 100₴/час."""
    return Zone(id=1, name="VIP", hourly_rate=Decimal("100.00"))


@pytest.fixture
def booking_create_valid():
    """Валидная схема создания бронирования на 2 часа вперед."""
    now = datetime.now(timezone.utc)
    return BookingCreate(
        pc_id=1,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=3),
    )


# ============================================================================
# ТЕСТЫ: create_booking - SUCCESS CASES
# ============================================================================


@pytest.mark.unit
async def test_create_booking_success(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_zone_repo,
    mock_booking_repo,
    sample_user,
    sample_pc,
    sample_zone,
    booking_create_valid,
):
    """Success: Успешное создание брони с корректным расчетом стоимости."""
    # Arrange
    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = False
    mock_zone_repo.get.return_value = sample_zone

    initial_balance = sample_user.balance

    # Mock для Celery tasks
    with patch("app.services.booking.send_receipt") as mock_send_receipt, patch(
        "app.services.booking.send_booking_reminder"
    ) as mock_send_reminder, patch("app.services.booking.manager") as mock_manager:
        mock_send_receipt.delay = MagicMock()
        mock_send_reminder.apply_async = MagicMock()
        mock_manager.broadcast_pc_update = AsyncMock()

        # Act
        await booking_service.create_booking(
            mock_db, booking_in=booking_create_valid, current_user=sample_user
        )

    # Assert
    # Проверяем расчет стоимости: 2 часа * 100₴ = 200₴
    duration_hours = (
        booking_create_valid.end_time - booking_create_valid.start_time
    ).total_seconds() / 3600
    expected_cost = Decimal(str(duration_hours)) * sample_zone.hourly_rate
    expected_cost = round(expected_cost, 2)

    assert sample_user.balance == initial_balance - expected_cost
    assert mock_db.add.call_count == 2  # booking + transaction
    assert mock_db.commit.called
    mock_send_receipt.delay.assert_called_once()


@pytest.mark.unit
async def test_create_booking_calculates_cost_correctly_for_fractional_hours(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_zone_repo,
    mock_booking_repo,
    sample_user,
    sample_pc,
    sample_zone,
):
    """Success: Правильный расчет стоимости для дробных часов (2.5 часа)."""
    # Arrange
    now = datetime.now(timezone.utc)
    booking_create = BookingCreate(
        pc_id=1,
        start_time=now + timedelta(hours=1),
        end_time=now + timedelta(hours=3, minutes=30),  # 1 час + 2.5 часа = 2.5 часа длительность
    )

    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = False
    mock_zone_repo.get.return_value = sample_zone

    with patch("app.services.booking.send_receipt"), patch(
        "app.services.booking.send_booking_reminder"
    ), patch("app.services.booking.manager") as mock_manager:
        mock_manager.broadcast_pc_update = AsyncMock()

        # Act
        await booking_service.create_booking(
            mock_db, booking_in=booking_create, current_user=sample_user
        )

    # Assert
    # 2.5 часа * 100₴ = 250₴
    expected_cost = Decimal("250.00")
    expected_balance = Decimal("1000.00") - expected_cost
    assert sample_user.balance == expected_balance


# ============================================================================
# ТЕСТЫ: create_booking - VALIDATION FAILURES
# ============================================================================


@pytest.mark.unit
async def test_create_booking_fails_end_time_before_start_time():
    """Fail: Конечное время раньше начального (валидация Pydantic)."""
    # Arrange
    now = datetime.now(timezone.utc)

    # Act & Assert
    # Pydantic валидация выбросит ValueError при создании схемы
    with pytest.raises(ValueError, match="Minimal time of booking is 15 minutes"):
        BookingCreate(
            pc_id=1,
            start_time=now + timedelta(hours=3),
            end_time=now + timedelta(hours=1),  # раньше start_time
        )


@pytest.mark.unit
async def test_create_booking_fails_end_time_equals_start_time():
    """Fail: Конечное время равно начальному (валидация Pydantic)."""
    # Arrange
    now = datetime.now(timezone.utc)
    same_time = now + timedelta(hours=1)

    # Act & Assert
    with pytest.raises(ValueError, match="Minimal time of booking is 15 minutes"):
        BookingCreate(
            pc_id=1,
            start_time=same_time,
            end_time=same_time,
        )


@pytest.mark.unit
async def test_create_booking_fails_pc_not_found(
    booking_service,
    mock_db,
    mock_pc_repo,
    sample_user,
    booking_create_valid,
):
    """Fail: ПК с указанным ID не существует."""
    # Arrange
    mock_pc_repo.get_with_lock.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="PC not found"):
        await booking_service.create_booking(
            mock_db, booking_in=booking_create_valid, current_user=sample_user
        )


@pytest.mark.unit
async def test_create_booking_fails_pc_already_booked(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_booking_repo,
    sample_user,
    sample_pc,
    booking_create_valid,
):
    """Fail: ПК уже забронирован на выбранное время (overlap)."""
    # Arrange
    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = True  # есть пересечение

    # Act & Assert
    with pytest.raises(
        ValueError, match="This PC is already booked for this time"
    ):
        await booking_service.create_booking(
            mock_db, booking_in=booking_create_valid, current_user=sample_user
        )


@pytest.mark.unit
async def test_create_booking_fails_zone_not_found(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_zone_repo,
    mock_booking_repo,
    sample_user,
    sample_pc,
    booking_create_valid,
):
    """Fail: Зона для ПК не найдена."""
    # Arrange
    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = False
    mock_zone_repo.get.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Zone for this PC is not found"):
        await booking_service.create_booking(
            mock_db, booking_in=booking_create_valid, current_user=sample_user
        )


@pytest.mark.unit
async def test_create_booking_fails_insufficient_balance(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_zone_repo,
    mock_booking_repo,
    sample_pc,
    sample_zone,
    booking_create_valid,
):
    """Fail: Недостаточно средств на балансе пользователя."""
    # Arrange
    poor_user = User(
        id=2,
        email="poor@test.com",
        hashed_password="hashed",
        balance=Decimal("50.00"),  # только 50₴
        role="user",
    )

    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = False
    mock_zone_repo.get.return_value = sample_zone

    # Act & Assert
    with pytest.raises(ValueError, match="Недостаточно средств"):
        await booking_service.create_booking(
            mock_db, booking_in=booking_create_valid, current_user=poor_user
        )


@pytest.mark.unit
async def test_create_booking_fails_zero_balance(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_zone_repo,
    mock_booking_repo,
    sample_pc,
    sample_zone,
    booking_create_valid,
):
    """Fail: Баланс пользователя равен нулю."""
    # Arrange
    broke_user = User(
        id=3,
        email="broke@test.com",
        hashed_password="hashed",
        balance=Decimal("0.00"),
        role="user",
    )

    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = False
    mock_zone_repo.get.return_value = sample_zone

    # Act & Assert
    with pytest.raises(ValueError, match="Недостаточно средств"):
        await booking_service.create_booking(
            mock_db, booking_in=booking_create_valid, current_user=broke_user
        )


# ============================================================================
# ТЕСТЫ: create_booking - EDGE CASES
# ============================================================================


@pytest.mark.unit
async def test_create_booking_with_exact_balance(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_zone_repo,
    mock_booking_repo,
    sample_pc,
    sample_zone,
    booking_create_valid,
):
    """Edge: Баланс пользователя точно равен стоимости бронирования."""
    # Arrange
    # Бронирование на 2 часа по 100₴ = 200₴
    exact_balance_user = User(
        id=4,
        email="exact@test.com",
        hashed_password="hashed",
        balance=Decimal("200.00"),
        role="user",
    )

    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = False
    mock_zone_repo.get.return_value = sample_zone

    with patch("app.services.booking.send_receipt"), patch(
        "app.services.booking.send_booking_reminder"
    ), patch("app.services.booking.manager") as mock_manager:
        mock_manager.broadcast_pc_update = AsyncMock()

        # Act
        await booking_service.create_booking(
            mock_db, booking_in=booking_create_valid, current_user=exact_balance_user
        )

    # Assert
    assert exact_balance_user.balance == Decimal("0.00")
    assert mock_db.add.call_count == 2


@pytest.mark.unit
async def test_create_booking_with_telegram_id_schedules_reminder(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_zone_repo,
    mock_booking_repo,
    sample_pc,
    sample_zone,
):
    """Success: Пользователь с telegram_id может получить напоминание (если countdown > 0)."""
    # Arrange
    telegram_user = User(
        id=5,
        email="telegram@test.com",
        hashed_password="hashed",
        balance=Decimal("1000.00"),
        role="user",
        telegram_id=123456789,
    )

    # Создаем бронь достаточно далеко в будущем
    now = datetime.now(timezone.utc)
    booking_create = BookingCreate(
        pc_id=1,
        start_time=now + timedelta(hours=5),
        end_time=now + timedelta(hours=7),  # 2 часа длительность, за 5 часов
    )

    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = False
    mock_zone_repo.get.return_value = sample_zone

    with patch("app.services.booking.send_receipt"), patch(
        "app.services.booking.send_booking_reminder"
    ) as mock_send_reminder, patch("app.services.booking.manager") as mock_manager, patch(
        "app.services.booking.datetime"
    ) as mock_datetime:
        # Мокаем datetime.now для контроля countdown_seconds
        mock_datetime.now.return_value = now
        mock_send_reminder.apply_async = MagicMock()
        mock_manager.broadcast_pc_update = AsyncMock()

        # Act
        await booking_service.create_booking(
            mock_db, booking_in=booking_create, current_user=telegram_user
        )

    # Assert
    # Напоминание должно быть запланировано, т.к. countdown положительный
    mock_send_reminder.apply_async.assert_called_once()


@pytest.mark.unit
async def test_create_booking_without_telegram_id_no_reminder(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_zone_repo,
    mock_booking_repo,
    sample_user,
    sample_pc,
    sample_zone,
    booking_create_valid,
):
    """Success: Пользователь без telegram_id не получает напоминание."""
    # Arrange
    sample_user.telegram_id = None

    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = False
    mock_zone_repo.get.return_value = sample_zone

    with patch("app.services.booking.send_receipt"), patch(
        "app.services.booking.send_booking_reminder"
    ) as mock_send_reminder, patch("app.services.booking.manager") as mock_manager:
        mock_send_reminder.apply_async = MagicMock()
        mock_manager.broadcast_pc_update = AsyncMock()

        # Act
        await booking_service.create_booking(
            mock_db, booking_in=booking_create_valid, current_user=sample_user
        )

    # Assert
    mock_send_reminder.apply_async.assert_not_called()


# ============================================================================
# ТЕСТЫ: cancel_booking
# ============================================================================


@pytest.mark.unit
async def test_cancel_booking_success_by_owner(
    booking_service,
    mock_db,
    mock_booking_repo,
    sample_user,
):
    """Success: Владелец успешно отменяет свою бронь."""
    # Arrange
    booking = Booking(
        id=1,
        user_id=sample_user.id,
        pc_id=1,
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        total_cost=Decimal("100.00"),
        status="active",
    )
    mock_booking_repo.get.return_value = booking
    mock_booking_repo.cancel_booking = AsyncMock()

    with patch("app.services.booking.manager") as mock_manager:
        mock_manager.broadcast_pc_update = AsyncMock()

        # Act
        result = await booking_service.cancel_booking(
            mock_db, booking_id=1, current_user=sample_user
        )

    # Assert
    assert result is True
    mock_booking_repo.cancel_booking.assert_called_once_with(mock_db, booking)
    mock_manager.broadcast_pc_update.assert_called_once()


@pytest.mark.unit
async def test_cancel_booking_success_by_admin(
    booking_service,
    mock_db,
    mock_booking_repo,
):
    """Success: Админ может отменить чужую бронь."""
    # Arrange
    admin_user = User(
        id=99,
        email="admin@test.com",
        hashed_password="hashed",
        balance=Decimal("0.00"),
        role="admin",
    )

    booking = Booking(
        id=1,
        user_id=1,  # другой пользователь
        pc_id=1,
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        total_cost=Decimal("100.00"),
        status="active",
    )
    mock_booking_repo.get.return_value = booking
    mock_booking_repo.cancel_booking = AsyncMock()

    with patch("app.services.booking.manager") as mock_manager:
        mock_manager.broadcast_pc_update = AsyncMock()

        # Act
        result = await booking_service.cancel_booking(
            mock_db, booking_id=1, current_user=admin_user
        )

    # Assert
    assert result is True


@pytest.mark.unit
async def test_cancel_booking_not_found(
    booking_service,
    mock_db,
    mock_booking_repo,
    sample_user,
):
    """Fail: Бронирование не найдено."""
    # Arrange
    mock_booking_repo.get.return_value = None

    # Act
    result = await booking_service.cancel_booking(
        mock_db, booking_id=999, current_user=sample_user
    )

    # Assert
    assert result is False


@pytest.mark.unit
async def test_cancel_booking_forbidden_other_user(
    booking_service,
    mock_db,
    mock_booking_repo,
):
    """Fail: Обычный пользователь не может отменить чужую бронь."""
    # Arrange
    owner_user = User(id=1, email="owner@test.com", role="user")
    other_user = User(id=2, email="other@test.com", role="user")

    booking = Booking(
        id=1,
        user_id=owner_user.id,
        pc_id=1,
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        total_cost=Decimal("100.00"),
        status="active",
    )
    mock_booking_repo.get.return_value = booking

    # Act & Assert
    with pytest.raises(
        PermissionError, match="You do not have the right to cancel this booking"
    ):
        await booking_service.cancel_booking(
            mock_db, booking_id=1, current_user=other_user
        )


@pytest.mark.unit
async def test_cancel_booking_idempotent_already_cancelled(
    booking_service,
    mock_db,
    mock_booking_repo,
    sample_user,
):
    """Success: Повторная отмена уже отмененной брони возвращает True (идемпотентность)."""
    # Arrange
    booking = Booking(
        id=1,
        user_id=sample_user.id,
        pc_id=1,
        start_time=datetime.now(timezone.utc) + timedelta(hours=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=2),
        total_cost=Decimal("100.00"),
        status="cancelled",  # уже отменена
    )
    mock_booking_repo.get.return_value = booking

    # Act
    result = await booking_service.cancel_booking(
        mock_db, booking_id=1, current_user=sample_user
    )

    # Assert
    assert result is True
    # cancel_booking не должен вызываться, если уже cancelled
    mock_booking_repo.cancel_booking.assert_not_called()


# ============================================================================
# ТЕСТЫ: create_cash_booking (базовая проверка изоляции)
# ============================================================================


@pytest.mark.unit
async def test_create_cash_booking_creates_guest_booking(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_zone_repo,
    mock_booking_repo,
    sample_pc,
    sample_zone,
    booking_create_valid,
):
    """Success: Касса создает бронь для гостевого пользователя."""
    # Arrange
    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = False
    mock_zone_repo.get.return_value = sample_zone

    guest_user = User(
        id=999,
        email="guest@test.com",
        hashed_password="",
        balance=Decimal("0.00"),
        role="guest",
    )

    with patch(
        "app.services.booking.UserService.get_or_create_guest_user"
    ) as mock_get_guest, patch("app.services.booking.manager") as mock_manager:
        mock_get_guest.return_value = guest_user
        mock_manager.broadcast_pc_update = AsyncMock()

        # Act
        await booking_service.create_cash_booking(
            mock_db, booking_in=booking_create_valid
        )

    # Assert
    # Проверяем, что добавлены booking + transaction
    assert mock_db.add.call_count == 2
    assert mock_db.commit.called


@pytest.mark.unit
async def test_create_cash_booking_fails_pc_not_found(
    booking_service,
    mock_db,
    mock_pc_repo,
    booking_create_valid,
):
    """Fail: Касса не может создать бронь для несуществующего ПК."""
    # Arrange
    mock_pc_repo.get_with_lock.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Компьютер не найден"):
        await booking_service.create_cash_booking(
            mock_db, booking_in=booking_create_valid
        )


@pytest.mark.unit
async def test_create_cash_booking_fails_overlap(
    booking_service,
    mock_db,
    mock_pc_repo,
    mock_booking_repo,
    sample_pc,
    booking_create_valid,
):
    """Fail: Касса не может создать бронь при оверлапе."""
    # Arrange
    mock_pc_repo.get_with_lock.return_value = sample_pc
    mock_booking_repo.check_overlap.return_value = True

    # Act & Assert
    with pytest.raises(ValueError, match="уже забронирован"):
        await booking_service.create_cash_booking(
            mock_db, booking_in=booking_create_valid
        )


# ============================================================================
# ТЕСТЫ: admin_cancel_pc_session
# ============================================================================


@pytest.mark.unit
async def test_admin_cancel_pc_session_success(
    booking_service,
    mock_db,
    mock_booking_repo,
):
    """Success: Админ завершает активную сессию по pc_id."""
    # Arrange
    admin_user = User(id=99, email="admin@test.com", role="admin")

    active_booking = Booking(
        id=1,
        user_id=1,
        pc_id=5,
        start_time=datetime.now(timezone.utc) - timedelta(minutes=30),
        end_time=datetime.now(timezone.utc) + timedelta(hours=1),
        total_cost=Decimal("100.00"),
        status="active",
    )
    mock_booking_repo.get_active_booking_by_pc.return_value = active_booking
    mock_booking_repo.get.return_value = active_booking
    mock_booking_repo.cancel_booking = AsyncMock()

    with patch("app.services.booking.manager") as mock_manager:
        mock_manager.broadcast_pc_update = AsyncMock()

        # Act
        result = await booking_service.admin_cancel_pc_session(
            mock_db, pc_id=5, admin_user=admin_user
        )

    # Assert
    assert result == active_booking
    mock_booking_repo.cancel_booking.assert_called_once()


@pytest.mark.unit
async def test_admin_cancel_pc_session_not_found(
    booking_service,
    mock_db,
    mock_booking_repo,
):
    """Fail: Нет активной сессии для указанного ПК."""
    # Arrange
    admin_user = User(id=99, email="admin@test.com", role="admin")
    mock_booking_repo.get_active_booking_by_pc.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Активная сессия для ПК 5 не найдена"):
        await booking_service.admin_cancel_pc_session(
            mock_db, pc_id=5, admin_user=admin_user
        )
