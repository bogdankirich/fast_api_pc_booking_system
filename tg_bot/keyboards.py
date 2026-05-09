from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_start_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🔑 Войти")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_main_menu() -> ReplyKeyboardMarkup:
    keyboard = [
        [KeyboardButton(text="🖥 Забронировать ПК")],
        [KeyboardButton(text="📅 Мои брони")],
        [KeyboardButton(text="⚙️ Настройки профиля")],
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
