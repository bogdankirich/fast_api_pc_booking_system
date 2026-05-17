from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, User

from tg_bot.handlers.auth import (
    LoginStates,
    cmd_login,
    process_email,
    process_password,
)


@pytest.mark.asyncio
async def test_cmd_login_starts_flow(message: Message, fsm_context: FSMContext) -> None:
    await cmd_login(message, fsm_context)

    mock_answer = cast(AsyncMock, message.answer)
    mock_answer.assert_called_once_with("Введите ваш email:")

    current_state = await fsm_context.get_state()
    assert current_state == LoginStates.waiting_for_email.state


@pytest.mark.asyncio
async def test_process_email_saves_and_asks_password(
    message: Message, fsm_context: FSMContext
) -> None:
    message.text = "user@example.com"
    await fsm_context.set_state(LoginStates.waiting_for_email)

    await process_email(message, fsm_context)

    user_data = await fsm_context.get_data()
    assert user_data["email"] == "user@example.com"

    mock_answer = cast(AsyncMock, message.answer)
    mock_answer.assert_called_once_with("Введите ваш пароль:")

    current_state = await fsm_context.get_state()
    assert current_state == LoginStates.waiting_for_password.state


@pytest.mark.asyncio
async def test_process_email_handles_empty_text(
    message: Message, fsm_context: FSMContext
) -> None:
    message.text = None
    await fsm_context.set_state(LoginStates.waiting_for_email)

    await process_email(message, fsm_context)

    mock_answer = cast(AsyncMock, message.answer)
    mock_answer.assert_called_once_with("Пожалуйста, отправьте email текстом.")


@pytest.mark.asyncio
async def test_process_password_successful_login(
    message: Message, fsm_context: FSMContext, mock_httpx_client: AsyncMock
) -> None:
    message.text = "password123"
    message.from_user = User(
        id=123456789,
        is_bot=False,
        first_name="Test",
    )

    await fsm_context.set_state(LoginStates.waiting_for_password)
    await fsm_context.update_data(email="user@example.com")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "new_access_token",
        "refresh_token": "new_refresh_token",
    }
    mock_httpx_client.post.return_value = mock_response

    mock_api_client = AsyncMock()
    mock_api_client.request.return_value = MagicMock(status_code=200)

    with (
        patch("httpx.AsyncClient", return_value=mock_httpx_client),
        patch("tg_bot.handlers.auth.api_client", mock_api_client),
        patch("tg_bot.handlers.auth.get_main_menu"),
    ):
        await process_password(message, fsm_context)

    mock_httpx_client.post.assert_called_once()
    call_args = mock_httpx_client.post.call_args
    assert call_args[0][0] == "http://web:8000/api/v1/login"
    assert call_args[1]["data"]["username"] == "user@example.com"
    assert call_args[1]["data"]["password"] == "password123"

    user_data = await fsm_context.get_data()
    assert user_data["access_token"] == "new_access_token"
    assert user_data["refresh_token"] == "new_refresh_token"

    mock_api_client.request.assert_called_once()
    patch_call_args = mock_api_client.request.call_args
    assert patch_call_args[1]["method"] == "PATCH"
    assert patch_call_args[1]["endpoint"] == "/api/v1/users/me"
    assert patch_call_args[1]["json"]["telegram_id"] == 123456789

    mock_answer = cast(AsyncMock, message.answer)
    mock_answer.assert_called_once()
    assert "успешно вошли" in mock_answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_password_invalid_credentials(
    message: Message, fsm_context: FSMContext, mock_httpx_client: AsyncMock
) -> None:
    message.text = "wrong_password"

    await fsm_context.set_state(LoginStates.waiting_for_password)
    await fsm_context.update_data(email="user@example.com")

    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"detail": "Неверный email или пароль"}
    mock_httpx_client.post.return_value = mock_response

    with (
        patch("httpx.AsyncClient", return_value=mock_httpx_client),
        patch("tg_bot.handlers.auth.get_start_menu"),
    ):
        await process_password(message, fsm_context)

    mock_answer = cast(AsyncMock, message.answer)
    mock_answer.assert_called_once()
    assert "Ошибка: Неверный email или пароль" in mock_answer.call_args[0][0]

    user_data = await fsm_context.get_data()
    assert user_data == {}


@pytest.mark.asyncio
async def test_process_password_server_error(
    message: Message, fsm_context: FSMContext, mock_httpx_client: AsyncMock
) -> None:
    message.text = "password123"

    await fsm_context.set_state(LoginStates.waiting_for_password)
    await fsm_context.update_data(email="user@example.com")

    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_httpx_client.post.return_value = mock_response

    with (
        patch("httpx.AsyncClient", return_value=mock_httpx_client),
        patch("tg_bot.handlers.auth.get_start_menu"),
    ):
        await process_password(message, fsm_context)

    mock_answer = cast(AsyncMock, message.answer)
    mock_answer.assert_called_once()
    assert "Ошибка сервера: 500" in mock_answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_password_connection_error(
    message: Message, fsm_context: FSMContext, mock_httpx_client: AsyncMock
) -> None:
    message.text = "password123"

    await fsm_context.set_state(LoginStates.waiting_for_password)
    await fsm_context.update_data(email="user@example.com")

    mock_httpx_client.post.side_effect = httpx.RequestError("Connection failed")

    with (
        patch("httpx.AsyncClient", return_value=mock_httpx_client),
        patch("tg_bot.handlers.auth.get_start_menu"),
    ):
        await process_password(message, fsm_context)

    mock_answer = cast(AsyncMock, message.answer)
    mock_answer.assert_called_once()
    assert "Ошибка подключения к API" in mock_answer.call_args[0][0]


@pytest.mark.asyncio
async def test_process_password_handles_empty_text(
    message: Message, fsm_context: FSMContext
) -> None:
    message.text = None
    await fsm_context.set_state(LoginStates.waiting_for_password)

    await process_password(message, fsm_context)

    mock_answer = cast(AsyncMock, message.answer)
    mock_answer.assert_called_once_with("Пожалуйста, отправьте пароль текстом.")


@pytest.mark.asyncio
async def test_process_password_telegram_id_binding_failure(
    message: Message, fsm_context: FSMContext, mock_httpx_client: AsyncMock
) -> None:
    message.text = "password123"
    message.from_user = User(id=123456789, is_bot=False, first_name="Test")

    await fsm_context.set_state(LoginStates.waiting_for_password)
    await fsm_context.update_data(email="user@example.com")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "token",
        "refresh_token": "refresh",
    }
    mock_httpx_client.post.return_value = mock_response

    mock_api_client = AsyncMock()
    mock_api_client.request.side_effect = Exception("API error")

    with (
        patch("httpx.AsyncClient", return_value=mock_httpx_client),
        patch("tg_bot.handlers.auth.api_client", mock_api_client),
        patch("tg_bot.handlers.auth.get_main_menu"),
    ):
        await process_password(message, fsm_context)

    mock_answer = cast(AsyncMock, message.answer)
    mock_answer.assert_called_once()
    assert "успешно вошли" in mock_answer.call_args[0][0]
