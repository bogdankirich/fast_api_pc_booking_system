# Unit-тесты для сервисов PC Booking System

## Обзор

Созданы качественные изолированные unit-тесты для критических сервисных модулей:

- ✅ **app/services/user.py** — 33% → **100%** покрытие (21 тест)
- ✅ **app/services/pc.py** — 39% → **100%** покрытие (21 тест)
- ⚠️ **app/locker_client.py** — GUI приложение, требует отдельного подхода к тестированию

**Итого: 42 unit-теста, все проходят успешно ✓**

---

## Структура тестов

```
tests/
└── services/
    ├── test_user_service.py       # 21 тест для UserService
    └── test_pc_service.py          # 21 тест для PCService
```

---

## Запуск тестов

### Все unit-тесты сервисов
```bash
docker compose exec web pytest tests/services/test_user_service.py tests/services/test_pc_service.py -v
```

### С покрытием кода
```bash
docker compose exec web pytest tests/services/ -v --cov=app/services --cov-report=term-missing
```

### Только тесты с маркером @pytest.mark.unit
```bash
docker compose exec web pytest -m unit
```

---

## Покрытие по модулям

### app/services/user.py — 100% ✓

**Покрыто:**
- ✅ `create_user` — создание с хешированием пароля, проверка дубликатов email
- ✅ `get_user` — получение пользователя по ID
- ✅ `authenticate_user` — аутентификация с verify_password
- ✅ `get_or_create_google_user` — OAuth Google пользователи
- ✅ `update_user` — обновление telegram_id
- ✅ `get_or_create_guest_user` — гостевой пользователь для кассы

**Сценарии:**
- ✅ Успешное создание пользователя с хешированием пароля
- ✅ Ошибка при дубликате email (обычная регистрация)
- ✅ Ошибка при попытке регистрации email, зарегистрированного через Google
- ✅ Успешная аутентификация с корректным паролем
- ✅ Ошибка аутентификации при неверном пароле
- ✅ Ошибка аутентификации для Google-пользователей (нет hashed_password)
- ✅ Создание/получение Google пользователя (идемпотентность)
- ✅ Обновление данных пользователя (только указанные поля)
- ✅ Создание/получение гостевого пользователя (идемпотентность)

---

### app/services/pc.py — 100% ✓

**Покрыто:**
- ✅ `create_pc` — создание ПК с валидацией зоны
- ✅ `get_pc` — получение статуса ПК на основе бронирований
- ✅ `get_pcs_by_zone` — список ПК зоны с рассчитанными статусами
- ✅ `get_available_pcs` — доступные ПК для временного интервала

**Сценарии:**
- ✅ Успешное создание ПК с валидной зоной
- ✅ Ошибка при создании ПК с несуществующей зоной
- ✅ ПК доступен когда нет бронирований
- ✅ ПК занят при активном бронировании (status: active/paid/SUCCESS)
- ✅ ПК доступен когда бронирование в будущем или прошлом
- ✅ Игнорирование отмененных (cancelled) и неоплаченных (pending) бронирований
- ✅ Граничные случаи времени (start_time == now, end_time == now)
- ✅ Множественные бронирования (приоритет текущего активного)
- ✅ Валидация временных интервалов (start >= end)
- ✅ Получение списка ПК по зоне с корректными статусами

---

## Ключевые особенности тестов

### ✅ Строгая изоляция
- Все внешние зависимости (repos, security functions) замокированы через `AsyncMock` и `MagicMock`
- Нет реальных запросов к БД или внешним сервисам
- Быстрое выполнение (5-6 секунд на 42 теста)

### ✅ Маркировка
- Все тесты помечены декоратором `@pytest.mark.unit`
- Легко фильтровать: `pytest -m unit`

### ✅ Покрытие edge cases
- Граничные значения (exact time boundaries)
- Нулевые/пустые значения (balance=0, empty lists)
- Дубликаты и конфликты (email exists, overlap bookings)
- Множественные состояния (cancelled, pending, active)

### ✅ Тестирование безопасности
- Хеширование паролей (plain password не попадает в БД)
- Проверка что `verify_password` не вызывается для несуществующих пользователей
- Google OAuth пользователи без пароля

### ✅ Читаемая структура
- Arrange-Act-Assert паттерн
- Описательные имена тестов (test_create_user_fails_email_already_exists)
- Docstrings с пометками Success/Fail/Edge

---

## Примеры тестов

### UserService: Создание пользователя с хешированием

```python
@pytest.mark.unit
async def test_create_user_success(user_service, mock_db, mock_user_repo, valid_user_create):
    """Success: Успешное создание нового пользователя с хешированием пароля."""
    # Arrange
    mock_user_repo.get_by_email.return_value = None

    with patch("app.services.user.get_password_hash") as mock_hash:
        mock_hash.return_value = "$2b$12$hashed_secure_pass"

        # Act
        result = await user_service.create_user(mock_db, user_in=valid_user_create)

    # Assert
    mock_hash.assert_called_once_with("SecurePass123!")
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    
    added_user = mock_db.add.call_args[0][0]
    assert added_user.email == "newuser@test.com"
    assert added_user.hashed_password == "$2b$12$hashed_secure_pass"
```

### PCService: Логика статуса ПК на основе бронирований

```python
@pytest.mark.unit
async def test_get_pc_returns_occupied_when_active_booking_now(
    pc_service, mock_db, mock_pc_repo, sample_pc, kyiv_now
):
    """Success: ПК занят когда есть активное бронирование СЕЙЧАС."""
    # Arrange
    active_booking = Booking(
        id=1, user_id=1, pc_id=1,
        start_time=kyiv_now - timedelta(minutes=30),  # началось 30 мин назад
        end_time=kyiv_now + timedelta(minutes=30),    # закончится через 30 мин
        status="active",
        total_cost=100.0,
    )
    sample_pc.bookings = [active_booking]
    mock_pc_repo.get_pc_with_bookings.return_value = sample_pc

    # Act
    result = await pc_service.get_pc(mock_db, pc_id=1)

    # Assert
    assert result.status == "occupied"
```

---

## Метрики

| Модуль | До | После | Тесты | Статус |
|--------|-----|-------|-------|---------|
| **app/services/user.py** | 33% | **100%** ✓ | 21 | ✅ Все проходят |
| **app/services/pc.py** | 39% | **100%** ✓ | 21 | ✅ Все проходят |
| **app/locker_client.py** | 0% | 0% | 0 | ⚠️ GUI приложение |

**Общее покрытие проекта: 46% → 52%** (+6%)

---

## Что НЕ покрыто (locker_client.py)

`app/locker_client.py` — это GUI приложение на customtkinter для блокировки ПК клиента.

**Проблемы тестирования:**
- Требует display/X11 для инициализации tkinter
- Не является модулем Python пакета (standalone script)
- Сложно изолировать GUI логику от бизнес-логики

**Рекомендации:**
1. Вынести бизнес-логику (HTTP запросы, определение статуса) в отдельный модуль
2. Протестировать логику отдельно от GUI
3. Использовать integration тесты для GUI части

---

## Зависимости

Все тесты используют:
- `pytest` — test runner
- `pytest-asyncio` — поддержка async тестов
- `unittest.mock` — AsyncMock, MagicMock, patch
- `pytest.mark.unit` — маркировка unit-тестов

Никаких дополнительных зависимостей не требуется.

---

## Дальнейшее развитие

### Приоритет 1: Высокое покрытие критических модулей ✓
- ✅ UserService — 100%
- ✅ PCService — 100%

### Приоритет 2: Другие сервисы
- [ ] BookingService (уже есть 97% покрытие)
- [ ] PaymentService
- [ ] ZoneService

### Приоритет 3: Репозитории
- [ ] UserRepository
- [ ] PCRepository
- [ ] BookingRepository

### Приоритет 4: Интеграционные тесты
- [ ] API endpoints (с тестовой БД)
- [ ] WebSocket соединения
- [ ] Celery tasks

---

## Авторы

Тесты созданы: 2026-06-13

## Лицензия

Соответствует лицензии основного проекта.
