from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Chat, Message, User

from tg_bot.utils.api_client import APIClient


@pytest.fixture(autouse=True)
async def setup_test_db():
    """
    Пустая фикстура-заглушка.
    Она перекрывает setup_test_db из корневого tests/conftest.py,
    чтобы тесты бота не пытались подключаться к тестовой базе данных.
    """
    yield


@pytest.fixture
def bot_user() -> User:
    return User(
        id=123456789,
        is_bot=False,
        first_name="Test",
        last_name="User",
        username="testuser",
        language_code="ru",
    )


@pytest.fixture
def chat() -> Chat:
    return Chat(id=123456789, type="private")


@pytest.fixture
def message(bot_user: User, chat: Chat) -> Message:
    msg = MagicMock(spec=Message)
    msg.from_user = bot_user
    msg.chat = chat
    msg.text = None
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    return msg


@pytest.fixture
def callback_query(bot_user: User, message: Message) -> CallbackQuery:
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = bot_user
    callback.message = message
    callback.data = None
    callback.answer = AsyncMock()
    return callback


@pytest.fixture
async def fsm_context() -> FSMContext:
    storage = MemoryStorage()
    key = StorageKey(bot_id=1, chat_id=123456789, user_id=123456789)
    return FSMContext(storage=storage, key=key)


@pytest.fixture
async def authenticated_fsm_context(fsm_context: FSMContext) -> FSMContext:
    await fsm_context.update_data(
        access_token="test_access_token",
        refresh_token="test_refresh_token",
    )
    return fsm_context


@pytest.fixture
def mock_api_client() -> AsyncMock:
    mock_client = AsyncMock(spec=APIClient)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "test@example.com",
        "role": "user",
        "balance": 100.50,
    }

    mock_client.get.return_value = mock_response
    mock_client.post.return_value = mock_response
    mock_client.request.return_value = mock_response

    return mock_client


@pytest.fixture
def mock_httpx_client() -> AsyncMock:
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
    }

    mock_client.post.return_value = mock_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    return mock_client
