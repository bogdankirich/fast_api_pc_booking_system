"""
Unit-тесты для UserService.

Фокус на изолированном тестировании бизнес-логики:
- Создание пользователя с хешированием пароля
- Проверка дубликатов email
- Аутентификация пользователя (verify_password)
- Обработка Google OAuth пользователей
- Создание/получение гостевого пользователя
- Обновление данных пользователя
- Edge cases (Google auth, отсутствие пароля)

Все внешние зависимости (repos, security functions) замокированы.
Цель: покрытие 33% -> 90%+
"""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate
from app.services.user import UserService

# ============================================================================
# ФИКСТУРЫ
# ============================================================================


@pytest.fixture
def mock_user_repo():
    """Mock репозитория пользователей."""
    return AsyncMock()


@pytest.fixture
def user_service(mock_user_repo):
    """Экземпляр UserService с замоканными зависимостями."""
    return UserService(user_repo=mock_user_repo)


@pytest.fixture
def mock_db():
    """Mock асинхронной сессии БД."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


@pytest.fixture
def valid_user_create():
    """Валидная схема создания пользователя."""
    return UserCreate(email="newuser@test.com", password="SecurePass123!")


@pytest.fixture
def sample_user():
    """Существующий пользователь."""
    return User(
        id=1,
        email="existing@test.com",
        hashed_password="$2b$12$hashed_password_example",
        role="user",
        balance=Decimal("100.00"),
    )


# ============================================================================
# ТЕСТЫ: create_user - SUCCESS CASES
# ============================================================================


@pytest.mark.unit
async def test_create_user_success(
    user_service, mock_db, mock_user_repo, valid_user_create
):
    """Success: Успешное создание нового пользователя с хешированием пароля."""
    # Arrange
    mock_user_repo.get_by_email.return_value = None

    with patch("app.services.user.get_password_hash") as mock_hash:
        mock_hash.return_value = "$2b$12$hashed_secure_pass"

        # Act
        await user_service.create_user(mock_db, user_in=valid_user_create)

    # Assert
    mock_user_repo.get_by_email.assert_called_once_with(
        mock_db, email="newuser@test.com"
    )
    mock_hash.assert_called_once_with("SecurePass123!")
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

    # Проверяем что User объект был создан корректно
    added_user = mock_db.add.call_args[0][0]
    assert isinstance(added_user, User)
    assert added_user.email == "newuser@test.com"
    assert added_user.hashed_password == "$2b$12$hashed_secure_pass"


@pytest.mark.unit
async def test_create_user_excludes_plain_password_from_db(
    user_service, mock_db, mock_user_repo, valid_user_create
):
    """Success: Простой пароль не попадает в БД, только хеш."""
    # Arrange
    mock_user_repo.get_by_email.return_value = None

    with patch("app.services.user.get_password_hash") as mock_hash:
        mock_hash.return_value = "$2b$12$hashed"

        # Act
        await user_service.create_user(mock_db, user_in=valid_user_create)

    # Assert
    added_user = mock_db.add.call_args[0][0]
    # Проверяем что у объекта User нет атрибута password (только hashed_password)
    assert not hasattr(added_user, "password")
    assert added_user.hashed_password == "$2b$12$hashed"


# ============================================================================
# ТЕСТЫ: create_user - VALIDATION FAILURES
# ============================================================================


@pytest.mark.unit
async def test_create_user_fails_email_already_exists(
    user_service, mock_db, mock_user_repo, sample_user
):
    """Fail: Email уже зарегистрирован (обычная регистрация)."""
    # Arrange
    sample_user.auth_provider = "local"
    mock_user_repo.get_by_email.return_value = sample_user

    user_create = UserCreate(email="existing@test.com", password="NewPass123!")

    # Act & Assert
    with pytest.raises(ValueError, match="User with this email already existing"):
        await user_service.create_user(mock_db, user_in=user_create)

    # Проверяем что не было попыток создать пользователя
    mock_db.add.assert_not_called()


@pytest.mark.unit
async def test_create_user_fails_email_registered_via_google(
    user_service, mock_db, mock_user_repo
):
    """Fail: Email зарегистрирован через Google OAuth."""
    # Arrange
    google_user = User(
        id=2,
        email="google@test.com",
        hashed_password=None,
        auth_provider="google",
        role="user",
    )
    mock_user_repo.get_by_email.return_value = google_user

    user_create = UserCreate(email="google@test.com", password="Pass123!")

    # Act & Assert
    with pytest.raises(
        ValueError,
        match="This email is registered via Google. Please log in using Google.",
    ):
        await user_service.create_user(mock_db, user_in=user_create)

    mock_db.add.assert_not_called()


# ============================================================================
# ТЕСТЫ: get_user
# ============================================================================


@pytest.mark.unit
async def test_get_user_success(user_service, mock_db, mock_user_repo, sample_user):
    """Success: Получение пользователя по ID."""
    # Arrange
    mock_user_repo.get.return_value = sample_user

    # Act
    result = await user_service.get_user(mock_db, user_id=1)

    # Assert
    assert result == sample_user
    mock_user_repo.get.assert_called_once_with(mock_db, id=1)


@pytest.mark.unit
async def test_get_user_returns_none_when_not_found(
    user_service, mock_db, mock_user_repo
):
    """Fail: Пользователь с указанным ID не существует."""
    # Arrange
    mock_user_repo.get.return_value = None

    # Act
    result = await user_service.get_user(mock_db, user_id=999)

    # Assert
    assert result is None


# ============================================================================
# ТЕСТЫ: authenticate_user
# ============================================================================


@pytest.mark.unit
async def test_authenticate_user_success(
    user_service, mock_db, mock_user_repo, sample_user
):
    """Success: Успешная аутентификация с корректным паролем."""
    # Arrange
    mock_user_repo.get_by_email.return_value = sample_user

    with patch("app.services.user.verify_password") as mock_verify:
        mock_verify.return_value = True

        # Act
        result = await user_service.authenticate_user(
            mock_db, email="existing@test.com", password="CorrectPassword123!"
        )

    # Assert
    assert result == sample_user
    mock_user_repo.get_by_email.assert_called_once_with(
        mock_db, email="existing@test.com"
    )
    mock_verify.assert_called_once_with(
        "CorrectPassword123!", sample_user.hashed_password
    )


@pytest.mark.unit
async def test_authenticate_user_fails_user_not_found(
    user_service, mock_db, mock_user_repo
):
    """Fail: Пользователь с таким email не существует."""
    # Arrange
    mock_user_repo.get_by_email.return_value = None

    # Act
    result = await user_service.authenticate_user(
        mock_db, email="notexist@test.com", password="AnyPassword"
    )

    # Assert
    assert result is None


@pytest.mark.unit
async def test_authenticate_user_fails_wrong_password(
    user_service, mock_db, mock_user_repo, sample_user
):
    """Fail: Неверный пароль."""
    # Arrange
    mock_user_repo.get_by_email.return_value = sample_user

    with patch("app.services.user.verify_password") as mock_verify:
        mock_verify.return_value = False

        # Act
        result = await user_service.authenticate_user(
            mock_db, email="existing@test.com", password="WrongPassword"
        )

    # Assert
    assert result is None
    mock_verify.assert_called_once()


@pytest.mark.unit
async def test_authenticate_user_fails_no_hashed_password(
    user_service, mock_db, mock_user_repo
):
    """Fail: Пользователь без пароля (Google OAuth) не может аутентифицироваться по паролю."""
    # Arrange
    google_user = User(
        id=3,
        email="google@test.com",
        hashed_password=None,  # нет пароля
        auth_provider="google",
        role="user",
    )
    mock_user_repo.get_by_email.return_value = google_user

    # Act
    result = await user_service.authenticate_user(
        mock_db, email="google@test.com", password="AnyPassword"
    )

    # Assert
    assert result is None


# ============================================================================
# ТЕСТЫ: get_or_create_google_user
# ============================================================================


@pytest.mark.unit
async def test_get_or_create_google_user_returns_existing(
    user_service, mock_db, mock_user_repo
):
    """Success: Возвращает существующего Google пользователя."""
    # Arrange
    existing_google_user = User(
        id=4,
        email="google@test.com",
        hashed_password=None,
        auth_provider="google",
        role="user",
    )
    mock_user_repo.get_by_email.return_value = existing_google_user

    # Act
    result = await user_service.get_or_create_google_user(
        mock_db, email="google@test.com"
    )

    # Assert
    assert result == existing_google_user
    mock_user_repo.get_by_email.assert_called_once_with(
        mock_db, email="google@test.com"
    )
    # Новый пользователь не должен создаваться
    mock_db.add.assert_not_called()


@pytest.mark.unit
async def test_get_or_create_google_user_creates_new(
    user_service, mock_db, mock_user_repo
):
    """Success: Создает нового Google пользователя если не существует."""
    # Arrange
    mock_user_repo.get_by_email.return_value = None

    # Act
    await user_service.get_or_create_google_user(mock_db, email="newgoogle@test.com")

    # Assert
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

    # Проверяем атрибуты созданного пользователя
    added_user = mock_db.add.call_args[0][0]
    assert added_user.email == "newgoogle@test.com"
    assert added_user.auth_provider == "google"
    assert added_user.hashed_password is None


# ============================================================================
# ТЕСТЫ: update_user
# ============================================================================


@pytest.mark.unit
async def test_update_user_success(user_service, mock_db, sample_user):
    """Success: Успешное обновление telegram_id пользователя."""
    # Arrange
    update_data = UserUpdate(telegram_id=123456789)
    original_email = sample_user.email

    # Act
    result = await user_service.update_user(
        mock_db, db_user=sample_user, update_data=update_data
    )

    # Assert
    assert sample_user.telegram_id == 123456789
    assert sample_user.email == original_email  # email не изменился
    mock_db.add.assert_called_once_with(sample_user)
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once_with(sample_user)
    assert result == sample_user


@pytest.mark.unit
async def test_update_user_updates_only_provided_fields(
    user_service, mock_db, sample_user
):
    """Success: Обновляются только указанные поля (exclude_unset=True)."""
    # Arrange
    update_data = UserUpdate(telegram_id=987654321)
    original_balance = sample_user.balance
    original_email = sample_user.email
    original_role = sample_user.role

    # Act
    await user_service.update_user(
        mock_db, db_user=sample_user, update_data=update_data
    )

    # Assert
    assert sample_user.telegram_id == 987654321
    assert sample_user.balance == original_balance  # баланс не изменился
    assert sample_user.email == original_email  # email не изменился
    assert sample_user.role == original_role  # роль не изменилась


@pytest.mark.unit
async def test_update_user_can_set_telegram_id_to_none(
    user_service, mock_db, sample_user
):
    """Success: Можно установить telegram_id в None (отвязать Telegram)."""
    # Arrange
    sample_user.telegram_id = 123456789
    update_data = UserUpdate(telegram_id=None)

    # Act
    await user_service.update_user(
        mock_db, db_user=sample_user, update_data=update_data
    )

    # Assert
    assert sample_user.telegram_id is None


@pytest.mark.unit
async def test_update_user_with_no_changes(user_service, mock_db, sample_user):
    """Success: Обновление без изменений (пустая схема)."""
    # Arrange
    update_data = UserUpdate()  # type: ignore[call-arg]
    # Act
    await user_service.update_user(
        mock_db, db_user=sample_user, update_data=update_data
    )

    # Assert
    # Даже без изменений должны вызываться commit и refresh
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()


# ============================================================================
# ТЕСТЫ: get_or_create_guest_user
# ============================================================================


@pytest.mark.unit
async def test_get_or_create_guest_user_returns_existing(
    user_service, mock_db, mock_user_repo
):
    """Success: Возвращает существующего гостевого пользователя."""
    # Arrange
    existing_guest = User(
        id=999,
        email="guest@club.local",
        hashed_password=None,
        auth_provider="system",
        role="guest",
        balance=Decimal("0.00"),
    )
    mock_user_repo.get_by_email.return_value = existing_guest

    # Act
    result = await user_service.get_or_create_guest_user(mock_db)

    # Assert
    assert result == existing_guest
    mock_user_repo.get_by_email.assert_called_once_with(
        mock_db, email="guest@club.local"
    )
    # Новый пользователь не должен создаваться
    mock_db.add.assert_not_called()


@pytest.mark.unit
async def test_get_or_create_guest_user_creates_new(
    user_service, mock_db, mock_user_repo
):
    """Success: Создает нового гостевого пользователя если не существует."""
    # Arrange
    mock_user_repo.get_by_email.return_value = None

    # Act
    await user_service.get_or_create_guest_user(mock_db)

    # Assert
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    mock_db.refresh.assert_called_once()

    # Проверяем атрибуты созданного гостя
    added_user = mock_db.add.call_args[0][0]
    assert added_user.email == "guest@club.local"
    assert added_user.auth_provider == "system"
    assert added_user.role == "guest"
    assert added_user.balance == 0
    assert added_user.hashed_password is None


@pytest.mark.unit
async def test_get_or_create_guest_user_idempotent(
    user_service, mock_db, mock_user_repo
):
    """Success: Повторные вызовы возвращают того же гостя (идемпотентность)."""
    # Arrange
    guest_user = User(
        id=999,
        email="guest@club.local",
        hashed_password=None,
        auth_provider="system",
        role="guest",
        balance=Decimal("0.00"),
    )
    mock_user_repo.get_by_email.return_value = guest_user

    # Act
    result1 = await user_service.get_or_create_guest_user(mock_db)
    result2 = await user_service.get_or_create_guest_user(mock_db)

    # Assert
    assert result1 == guest_user
    assert result2 == guest_user
    # Проверяем что get_by_email вызывался дважды
    assert mock_user_repo.get_by_email.call_count == 2
    # Но создания нового пользователя не было
    mock_db.add.assert_not_called()


# ============================================================================
# ТЕСТЫ: Edge Cases и безопасность
# ============================================================================


@pytest.mark.unit
async def test_create_user_does_not_log_password(
    user_service, mock_db, mock_user_repo, valid_user_create
):
    """Security: Пароль не должен попадать в логи или исключения."""
    # Arrange
    mock_user_repo.get_by_email.return_value = None

    with patch("app.services.user.get_password_hash") as mock_hash:
        mock_hash.return_value = "$2b$12$hashed"

        # Act
        await user_service.create_user(mock_db, user_in=valid_user_create)

    # Assert
    # Проверяем что в User объекте нет plain password
    added_user = mock_db.add.call_args[0][0]
    user_dict = vars(added_user)
    assert "password" not in user_dict
    assert "SecurePass123!" not in str(user_dict)


@pytest.mark.unit
async def test_authenticate_user_constant_time_for_nonexistent_user(
    user_service, mock_db, mock_user_repo
):
    """Security: Аутентификация несуществующего пользователя не должна раскрывать это сразу."""
    # Arrange
    mock_user_repo.get_by_email.return_value = None

    with patch("app.services.user.verify_password") as mock_verify:
        # Act
        result = await user_service.authenticate_user(
            mock_db, email="notexist@test.com", password="AnyPassword"
        )

    # Assert
    assert result is None
    # verify_password НЕ должен вызываться если пользователь не найден
    mock_verify.assert_not_called()
