from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from tg_bot.handlers.profile import callback_logout, callback_topup, cmd_profile


@pytest.mark.asyncio
async def test_cmd_profile_unauthorized(
    message: Message, fsm_context: FSMContext
) -> None:
    await cmd_profile(message, fsm_context)

    message.answer.assert_called_once_with(  # type: ignore
        "❌ Вы не авторизованы. Пожалуйста, войдите в систему."
    )


@pytest.mark.asyncio
async def test_cmd_profile_success_regular_user(
    message: Message,
    authenticated_fsm_context: FSMContext,
    mock_api_client: AsyncMock,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "gamer@example.com",
        "role": "user",
        "balance": 250.75,
    }
    mock_api_client.get.return_value = mock_response

    with patch("tg_bot.handlers.profile.api_client", mock_api_client):
        await cmd_profile(message, authenticated_fsm_context)

    mock_api_client.get.assert_called_once_with(
        "/api/v1/users/me", authenticated_fsm_context
    )

    message.answer.assert_called_once()  # type: ignore
    call_args = message.answer.call_args  # type: ignore
    text = call_args[0][0]

    assert "gamer@example.com" in text
    assert "👤 <b>Геймер</b>" in text
    assert "250.75 ₴" in text

    keyboard = call_args[1]["reply_markup"]
    assert isinstance(keyboard, InlineKeyboardMarkup)
    assert call_args[1]["parse_mode"] == "HTML"


@pytest.mark.asyncio
async def test_cmd_profile_success_admin_user(
    message: Message,
    authenticated_fsm_context: FSMContext,
    mock_api_client: AsyncMock,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "admin@example.com",
        "role": "admin",
        "balance": 0.00,
    }
    mock_api_client.get.return_value = mock_response

    with patch("tg_bot.handlers.profile.api_client", mock_api_client):
        await cmd_profile(message, authenticated_fsm_context)

    call_args = message.answer.call_args  # type: ignore
    text = call_args[0][0]

    assert "admin@example.com" in text
    assert "👑 <b>Администратор</b>" in text
    assert "0.00 ₴" in text


@pytest.mark.asyncio
async def test_cmd_profile_handles_null_balance(
    message: Message,
    authenticated_fsm_context: FSMContext,
    mock_api_client: AsyncMock,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "email": "test@example.com",
        "role": "user",
        "balance": None,
    }
    mock_api_client.get.return_value = mock_response

    with patch("tg_bot.handlers.profile.api_client", mock_api_client):
        await cmd_profile(message, authenticated_fsm_context)

    call_args = message.answer.call_args  # type: ignore
    text = call_args[0][0]

    assert "0.00 ₴" in text


@pytest.mark.asyncio
async def test_cmd_profile_api_error(
    message: Message,
    authenticated_fsm_context: FSMContext,
    mock_api_client: AsyncMock,
) -> None:
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_api_client.get.return_value = mock_response

    with patch("tg_bot.handlers.profile.api_client", mock_api_client):
        await cmd_profile(message, authenticated_fsm_context)

    message.answer.assert_called_once_with("❌ Ошибка получения данных: 500")  # type: ignore


@pytest.mark.asyncio
async def test_cmd_profile_exception_handling(
    message: Message,
    authenticated_fsm_context: FSMContext,
    mock_api_client: AsyncMock,
) -> None:
    mock_api_client.get.side_effect = Exception("Connection error")

    with patch("tg_bot.handlers.profile.api_client", mock_api_client):
        await cmd_profile(message, authenticated_fsm_context)

    message.answer.assert_called_once_with("❌ Ошибка: Connection error")  # type: ignore


@pytest.mark.asyncio
async def test_callback_logout_clears_state(
    callback_query: CallbackQuery, authenticated_fsm_context: FSMContext
) -> None:
    callback_query.data = "logout"

    with patch("tg_bot.handlers.profile.get_start_menu") as mock_menu:
        await callback_logout(callback_query, authenticated_fsm_context)

    user_data = await authenticated_fsm_context.get_data()
    assert user_data == {}

    callback_query.message.edit_text.assert_called_once_with(  # type: ignore
        "🚪 Вы успешно вышли из аккаунта"
    )
    callback_query.message.answer.assert_called_once()  # type: ignore
    callback_query.answer.assert_called_once()  # type: ignore


@pytest.mark.asyncio
async def test_callback_topup_unauthorized_shows_alert(
    callback_query: CallbackQuery,
) -> None:
    callback_query.data = "topup"

    # Создаем фейковый стейт, который вернет пустой словарь (без токена)
    mock_state = AsyncMock(spec=FSMContext)
    mock_state.get_data.return_value = {}

    # Передаем state в функцию!
    await callback_topup(callback_query, state=mock_state)

    callback_query.answer.assert_called_once()  # type: ignore
    call_args = callback_query.answer.call_args  # type: ignore

    # Проверяем новую логику ответа
    assert "Сессия истекла" in call_args[0][0]
    assert call_args[1]["show_alert"] is True
