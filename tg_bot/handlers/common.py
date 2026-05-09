from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from tg_bot.keyboards import get_start_menu

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Добро пожаловать в бот компьютерного клуба!\n\n"
        "Здесь вы можете:\n"
        "• Забронировать компьютер\n"
        "• Просмотреть свои бронирования\n"
        "• Управлять профилем\n\n"
        "Для начала работы войдите в систему 👇",
        reply_markup=get_start_menu(),
    )


@router.message(F.text == "⚙️ Настройки профиля")
async def settings_menu(message: Message):
    await message.answer(
        "⚙️ Настройки профиля\n\n"
        "Здесь будут настройки вашего профиля.\n"
        "Функционал в разработке."
    )
