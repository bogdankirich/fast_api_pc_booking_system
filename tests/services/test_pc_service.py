"""
Unit-тесты для PCService.

Фокус на изолированном тестировании бизнес-логики:
- Создание ПК и валидация зоны
- Получение статуса ПК с учетом активных бронирований
- Логика определения статуса (available/occupied) на основе временных интервалов
- Получение списка ПК по зоне
- Получение доступных ПК для бронирования
- Обработка edge cases (зона не найдена, временные интервалы)

Все внешние зависимости (repos) замокированы.
Цель: покрытие 39% -> 90%+
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest

from app.models.bookings import Booking
from app.models.pc import PC
from app.models.zone import Zone
from app.schemas.pc import PCCreate
from app.services.pc import PCService


# ============================================================================
# ФИКСТУРЫ
# ============================================================================


@pytest.fixture
def mock_pc_repo():
    """Mock репозитория ПК."""
    return AsyncMock()


@pytest.fixture
def mock_zone_repo():
    """Mock репозитория зон."""
    return AsyncMock()


@pytest.fixture
def pc_service(mock_pc_repo, mock_zone_repo):
    """Экземпляр PCService с замоканными зависимостями."""
    return PCService(pc_repo=mock_pc_repo, zone_repo=mock_zone_repo)


@pytest.fixture
def mock_db():
    """Mock асинхронной сессии БД."""
    return AsyncMock()


@pytest.fixture
def sample_zone():
    """Тестовая зона."""
    return Zone(id=1, name="VIP", hourly_rate=100.00)


@pytest.fixture
def sample_pc():
    """Тестовый ПК без бронирований."""
    pc = PC(id=1, mac_address="00:11:22:33:44:55", zone_id=1, status="available")
    pc.bookings = []
    return pc


@pytest.fixture
def kyiv_now():
    """Текущее время в киевской timezone (naive)."""
    return datetime.now(ZoneInfo("Europe/Kyiv")).replace(tzinfo=None)


# ============================================================================
# ТЕСТЫ: create_pc
# ============================================================================


@pytest.mark.unit
async def test_create_pc_success(
    pc_service, mock_db, mock_zone_repo, mock_pc_repo, sample_zone
):
    """Success: Успешное создание ПК с валидной зоной."""
    # Arrange
    pc_create = PCCreate(mac_address="AA:BB:CC:DD:EE:FF", zone_id=1)
    mock_zone_repo.get.return_value = sample_zone

    created_pc = PC(id=10, mac_address="AA:BB:CC:DD:EE:FF", zone_id=1)
    mock_pc_repo.create.return_value = created_pc

    # Act
    result = await pc_service.create_pc(mock_db, pc_in=pc_create)

    # Assert
    mock_zone_repo.get.assert_called_once_with(mock_db, id=1)
    mock_pc_repo.create.assert_called_once_with(mock_db, obj_in=pc_create)
    assert result == created_pc
    assert result.mac_address == "AA:BB:CC:DD:EE:FF"


@pytest.mark.unit
async def test_create_pc_fails_zone_not_found(
    pc_service, mock_db, mock_zone_repo, mock_pc_repo
):
    """Fail: Зона с указанным ID не существует."""
    # Arrange
    pc_create = PCCreate(mac_address="AA:BB:CC:DD:EE:FF", zone_id=999)
    mock_zone_repo.get.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Zone with ID 999 not found"):
        await pc_service.create_pc(mock_db, pc_in=pc_create)

    # Проверяем что репозиторий ПК не вызывался
    mock_pc_repo.create.assert_not_called()


# ============================================================================
# ТЕСТЫ: get_pc - Статус based на бронированиях
# ============================================================================


@pytest.mark.unit
async def test_get_pc_returns_available_when_no_bookings(
    pc_service, mock_db, mock_pc_repo, sample_pc
):
    """Success: ПК доступен когда нет бронирований."""
    # Arrange
    sample_pc.bookings = []
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    assert result is not None
    assert result.status == "available"
    mock_pc_repo.get_pc_with_bookings.assert_called_once_with(mock_db, 1)


@pytest.mark.unit
async def test_get_pc_returns_occupied_when_active_booking_now(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Success: ПК занят когда есть активное бронирование СЕЙЧАС."""
    # Arrange
    active_booking = Booking(
        id=1,
        user_id=1,
        pc_id=1,
        start_time=kyiv_now - timedelta(minutes=30),  # началось 30 мин назад
        end_time=kyiv_now + timedelta(minutes=30),  # закончится через 30 мин
        status="active",
        total_cost=100.0,
    )
    sample_pc.bookings = [active_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    assert result is not None
    assert result.status == "occupied"


@pytest.mark.unit
async def test_get_pc_returns_occupied_when_paid_booking_now(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Success: ПК занят когда есть оплаченное бронирование СЕЙЧАС."""
    # Arrange
    paid_booking = Booking(
        id=2,
        user_id=1,
        pc_id=1,
        start_time=kyiv_now - timedelta(hours=1),
        end_time=kyiv_now + timedelta(hours=1),
        status="paid",
        total_cost=200.0,
    )
    sample_pc.bookings = [paid_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    assert result.status == "occupied"


@pytest.mark.unit
async def test_get_pc_returns_occupied_when_success_booking_now(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Success: ПК занят когда есть SUCCESS бронирование СЕЙЧАС."""
    # Arrange
    success_booking = Booking(
        id=3,
        user_id=1,
        pc_id=1,
        start_time=kyiv_now - timedelta(minutes=15),
        end_time=kyiv_now + timedelta(minutes=45),
        status="SUCCESS",
        total_cost=100.0,
    )
    sample_pc.bookings = [success_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    assert result.status == "occupied"


@pytest.mark.unit
async def test_get_pc_returns_available_when_booking_in_future(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Success: ПК доступен когда бронирование только в будущем."""
    # Arrange
    future_booking = Booking(
        id=4,
        user_id=1,
        pc_id=1,
        start_time=kyiv_now + timedelta(hours=2),  # через 2 часа
        end_time=kyiv_now + timedelta(hours=4),
        status="active",
        total_cost=200.0,
    )
    sample_pc.bookings = [future_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    assert result.status == "available"


@pytest.mark.unit
async def test_get_pc_returns_available_when_booking_in_past(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Success: ПК доступен когда бронирование уже закончилось."""
    # Arrange
    past_booking = Booking(
        id=5,
        user_id=1,
        pc_id=1,
        start_time=kyiv_now - timedelta(hours=3),
        end_time=kyiv_now - timedelta(hours=1),  # закончилось час назад
        status="active",
        total_cost=200.0,
    )
    sample_pc.bookings = [past_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    assert result.status == "available"


@pytest.mark.unit
async def test_get_pc_ignores_cancelled_bookings(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Success: Отмененные бронирования не влияют на статус."""
    # Arrange
    cancelled_booking = Booking(
        id=6,
        user_id=1,
        pc_id=1,
        start_time=kyiv_now - timedelta(minutes=10),
        end_time=kyiv_now + timedelta(minutes=50),
        status="cancelled",  # отменено
        total_cost=100.0,
    )
    sample_pc.bookings = [cancelled_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    assert result.status == "available"


@pytest.mark.unit
async def test_get_pc_ignores_pending_bookings(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Success: Неоплаченные (pending) бронирования не занимают ПК."""
    # Arrange
    pending_booking = Booking(
        id=7,
        user_id=1,
        pc_id=1,
        start_time=kyiv_now - timedelta(minutes=5),
        end_time=kyiv_now + timedelta(minutes=55),
        status="pending",
        total_cost=100.0,
    )
    sample_pc.bookings = [pending_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    assert result.status == "available"


@pytest.mark.unit
async def test_get_pc_returns_occupied_with_multiple_bookings_one_active(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Success: При нескольких бронированиях, одно активное - ПК занят."""
    # Arrange
    past_booking = Booking(
        id=8,
        user_id=1,
        pc_id=1,
        start_time=kyiv_now - timedelta(hours=5),
        end_time=kyiv_now - timedelta(hours=3),
        status="active",
        total_cost=200.0,
    )
    current_booking = Booking(
        id=9,
        user_id=2,
        pc_id=1,
        start_time=kyiv_now - timedelta(minutes=10),
        end_time=kyiv_now + timedelta(minutes=50),
        status="paid",
        total_cost=100.0,
    )
    future_booking = Booking(
        id=10,
        user_id=3,
        pc_id=1,
        start_time=kyiv_now + timedelta(hours=2),
        end_time=kyiv_now + timedelta(hours=4),
        status="active",
        total_cost=200.0,
    )
    sample_pc.bookings = [past_booking, current_booking, future_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    # Есть текущее активное бронирование - должен быть occupied
    assert result.status == "occupied"


@pytest.mark.unit
async def test_get_pc_returns_none_when_not_found(
    pc_service, mock_db, mock_pc_repo
):
    """Fail: ПК с указанным ID не существует."""
    # Arrange
    mock_pc_repo.get_pc_with_bookings.return_value = None

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=999)

    # Assert
    assert result is None


@pytest.mark.unit
async def test_get_pc_boundary_start_time_exact(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Edge: Бронирование начинается РОВНО сейчас - ПК занят."""
    # Arrange
    exact_start_booking = Booking(
        id=11,
        user_id=1,
        pc_id=1,
        start_time=kyiv_now,  # начинается СЕЙЧАС
        end_time=kyiv_now + timedelta(hours=1),
        status="active",
        total_cost=100.0,
    )
    sample_pc.bookings = [exact_start_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    # start_time <= now <= end_time, должен быть occupied
    assert result.status == "occupied"


@pytest.mark.unit
async def test_get_pc_boundary_end_time_exact(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Edge: Бронирование заканчивается через секунду - ПК занят."""
    # Arrange
    # Логика: start_time <= now <= end_time
    # Если end_time == now, то now <= end_time верно, но на практике может быть погрешность
    # Поэтому используем end_time чуть больше now
    exact_end_booking = Booking(
        id=12,
        user_id=1,
        pc_id=1,
        start_time=kyiv_now - timedelta(hours=1),
        end_time=kyiv_now + timedelta(seconds=1),  # заканчивается через секунду
        status="active",
        total_cost=100.0,
    )
    sample_pc.bookings = [exact_end_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    # start_time <= now <= end_time, должен быть occupied
    assert result.status == "occupied"


# ============================================================================
# ТЕСТЫ: get_pcs_by_zone
# ============================================================================


@pytest.mark.unit
async def test_get_pcs_by_zone_returns_all_pcs_with_statuses(
    pc_service, mock_db, mock_pc_repo, kyiv_now
):
    """Success: Возвращает все ПК зоны с рассчитанными статусами."""
    # Arrange
    pc1 = PC(id=1, mac_address="AA:AA:AA:AA:AA:AA", zone_id=1, status="available")
    pc1.bookings = []

    pc2 = PC(id=2, mac_address="BB:BB:BB:BB:BB:BB", zone_id=1, status="available")
    active_booking = Booking(
        id=20,
        user_id=1,
        pc_id=2,
        start_time=kyiv_now - timedelta(minutes=30),
        end_time=kyiv_now + timedelta(minutes=30),
        status="active",
        total_cost=100.0,
    )
    pc2.bookings = [active_booking]

    mock_pc_repo.get_by_zone.return_value = [pc1, pc2]

    # Act
    result = await pc_service.get_pcs_by_zone(mock_db, zone_id=1)

    # Assert
    assert len(result) == 2
    assert result[0].status == "available"
    assert result[1].status == "occupied"
    mock_pc_repo.get_by_zone.assert_called_once_with(mock_db, zone_id=1)


@pytest.mark.unit
async def test_get_pcs_by_zone_returns_empty_list_when_no_pcs(
    pc_service, mock_db, mock_pc_repo
):
    """Success: Возвращает пустой список когда в зоне нет ПК."""
    # Arrange
    mock_pc_repo.get_by_zone.return_value = []

    # Act
    result = await pc_service.get_pcs_by_zone(mock_db, zone_id=999)

    # Assert
    assert result == []


# ============================================================================
# ТЕСТЫ: get_available_pcs
# ============================================================================


@pytest.mark.unit
async def test_get_available_pcs_success(
    pc_service, mock_db, mock_zone_repo, mock_pc_repo, sample_zone, kyiv_now
):
    """Success: Возвращает доступные ПК для заданного интервала."""
    # Arrange
    start_time = kyiv_now + timedelta(hours=1)
    end_time = kyiv_now + timedelta(hours=3)

    mock_zone_repo.get.return_value = sample_zone

    available_pcs = [
        PC(id=1, mac_address="AA:AA:AA:AA:AA:AA", zone_id=1),
        PC(id=2, mac_address="BB:BB:BB:BB:BB:BB", zone_id=1),
    ]
    mock_pc_repo.get_available_in_zone.return_value = available_pcs

    # Act
    result = await pc_service.get_available_pcs(
        mock_db, zone_id=1, start_time=start_time, end_time=end_time
    )

    # Assert
    assert len(result) == 2
    mock_zone_repo.get.assert_called_once_with(mock_db, id=1)
    mock_pc_repo.get_available_in_zone.assert_called_once_with(
        mock_db, zone_id=1, start_time=start_time, end_time=end_time
    )


@pytest.mark.unit
async def test_get_available_pcs_fails_start_after_end(
    pc_service, mock_db, kyiv_now
):
    """Fail: Начальное время позже конечного."""
    # Arrange
    start_time = kyiv_now + timedelta(hours=3)
    end_time = kyiv_now + timedelta(hours=1)

    # Act & Assert
    with pytest.raises(ValueError, match="Start time must be before end time"):
        await pc_service.get_available_pcs(
            mock_db, zone_id=1, start_time=start_time, end_time=end_time
        )


@pytest.mark.unit
async def test_get_available_pcs_fails_start_equals_end(
    pc_service, mock_db, kyiv_now
):
    """Fail: Начальное время равно конечному."""
    # Arrange
    same_time = kyiv_now + timedelta(hours=2)

    # Act & Assert
    with pytest.raises(ValueError, match="Start time must be before end time"):
        await pc_service.get_available_pcs(
            mock_db, zone_id=1, start_time=same_time, end_time=same_time
        )


@pytest.mark.unit
async def test_get_available_pcs_fails_zone_not_found(
    pc_service, mock_db, mock_zone_repo, mock_pc_repo, kyiv_now
):
    """Fail: Зона с указанным ID не существует."""
    # Arrange
    start_time = kyiv_now + timedelta(hours=1)
    end_time = kyiv_now + timedelta(hours=3)
    mock_zone_repo.get.return_value = None

    # Act & Assert
    with pytest.raises(ValueError, match="Zone with ID 999 not found"):
        await pc_service.get_available_pcs(
            mock_db, zone_id=999, start_time=start_time, end_time=end_time
        )

    # Проверяем что репозиторий ПК не вызывался
    mock_pc_repo.get_available_in_zone.assert_not_called()


@pytest.mark.unit
async def test_get_available_pcs_returns_empty_when_all_busy(
    pc_service, mock_db, mock_zone_repo, mock_pc_repo, sample_zone, kyiv_now
):
    """Success: Возвращает пустой список когда все ПК заняты."""
    # Arrange
    start_time = kyiv_now + timedelta(hours=1)
    end_time = kyiv_now + timedelta(hours=3)

    mock_zone_repo.get.return_value = sample_zone
    mock_pc_repo.get_available_in_zone.return_value = []

    # Act
    result = await pc_service.get_available_pcs(
        mock_db, zone_id=1, start_time=start_time, end_time=end_time
    )

    # Assert
    assert result == []
