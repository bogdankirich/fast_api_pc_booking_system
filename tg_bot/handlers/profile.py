from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from tg_bot.keyboards import get_start_menu
from tg_bot.utils.api_client import APIClient

router = Router()
api_client = APIClient()


@router.message(F.text == "⚙️ Настройки профиля")
async def cmd_profile(message: Message, state: FSMContext):
    user_data = await state.get_data()
    if not user_data.get("access_token"):
        await message.answer("❌ Вы не авторизованы. Пожалуйста, войдите в систему.")
        return

    try:
        response = await api_client.get("/api/v1/users/me", state)

        if response.status_code == 200:
            user_info = response.json()
            email = user_info.get("email", "Не указан")

            role = user_info.get("role")
            is_admin = role == "admin"

            status_text = "👑 <b>Администратор</b>" if is_admin else "👤 <b>Геймер</b>"

            try:
                balance = float(user_info.get("balance", 0.00) or 0.00)
            except (ValueError, TypeError):
                balance = 0.00

            text = (
                f"<b>Ваш профиль:</b>\n\n"
                f"👤 Email: <code>{email}</code>\n"
                f"🔰 Статус: {status_text}\n"
                f"💰 Баланс: {balance:.2f} ₴"
            )

            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💳 Пополнить баланс", callback_data="topup"
                        )
                    ],
                    [InlineKeyboardButton(text="🚪 Выйти", callback_data="logout")],
                ]
            )

            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(f"❌ Ошибка получения данных: {response.status_code}")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(F.data == "logout")
async def callback_logout(callback: CallbackQuery, state: FSMContext):

    await state.clear()

    if isinstance(callback.message, Message):
        await callback.message.edit_text("🚪 Вы успешно вышли из аккаунта")
        await callback.message.answer(
            "Для входа нажмите кнопку ниже:", reply_markup=get_start_menu()
        )
    else:
        await callback.answer("Вы вышли из системы")

    await callback.answer()


@router.callback_query(F.data == "topup")
async def callback_topup(callback: CallbackQuery):
    await callback.answer(
        "💳 Функция пополнения баланса появится после интеграции платежной системы.",
        show_alert=True,
    )
