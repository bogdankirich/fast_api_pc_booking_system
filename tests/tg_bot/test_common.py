from typing import cast
from unittest.mock import AsyncMock

import pytest
from aiogram.types import Message

from tg_bot.handlers.common import cmd_start
from tg_bot.keyboards import get_start_menu


@pytest.mark.asyncio
async def test_cmd_start_returns_welcome_message(message: Message) -> None:
    await cmd_start(message)

    mock_answer = cast(AsyncMock, message.answer)
    mock_answer.assert_called_once()
    call_args = mock_answer.call_args

    assert "Добро пожаловать" in call_args[0][0]
    assert "Забронировать компьютер" in call_args[0][0]
    assert "Просмотреть свои бронирования" in call_args[0][0]
    assert "Управлять профилем" in call_args[0][0]


@pytest.mark.asyncio
async def test_cmd_start_returns_start_menu_keyboard(message: Message) -> None:
    await cmd_start(message)

    mock_answer = cast(AsyncMock, message.answer)
    call_args = mock_answer.call_args
    keyboard = call_args[1]["reply_markup"]

    expected_keyboard = get_start_menu()
    assert keyboard.keyboard == expected_keyboard.keyboard
    assert keyboard.resize_keyboard == expected_keyboard.resize_keyboard
