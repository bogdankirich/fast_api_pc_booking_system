from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
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


class TopUpStates(StatesGroup):
    waiting_for_amount = State()


# --- ФАБРИКА КНОПОК ПРОФИЛЯ ---
class ProfileCallback(CallbackData, prefix="profile"):
    action: str  # 'topup' или 'logout'


@router.message(F.text == "⚙️ Настройки профиля")
async def cmd_profile(message: Message, state: FSMContext):
    user_data = await state.get_data()
    if not user_data.get("access_token"):
        await message.answer("❌ Вы не авторизованы. Пожалуйста, войдите в систему.")
        return

    try:
        # Явно указываем state=state
        response = await api_client.get("/api/v1/users/me", state=state)

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

            # Используем фабрику кнопок вместо сырых строк
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💳 Пополнить баланс",
                            callback_data=ProfileCallback(action="topup").pack(),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            text="🚪 Выйти",
                            callback_data=ProfileCallback(action="logout").pack(),
                        )
                    ],
                ]
            )

            await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        else:
            await message.answer(f"❌ Ошибка получения данных: {response.status_code}")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(ProfileCallback.filter(F.action == "logout"))
async def callback_logout(callback: CallbackQuery, state: FSMContext):
    # Страховка для линтера
    if not isinstance(callback.message, Message):
        return

    # При логауте нам действительно нужно удалить всё, включая токены
    await state.clear()

    await callback.message.edit_text("🚪 Вы успешно вышли из аккаунта")
    await callback.message.answer(
        "Для входа нажмите кнопку ниже:", reply_markup=get_start_menu()
    )
    await callback.answer()


@router.callback_query(ProfileCallback.filter(F.action == "topup"))
async def callback_topup(callback: CallbackQuery, state: FSMContext):
    if not isinstance(callback.message, Message):
        return

    user_data = await state.get_data()
    if not user_data.get("access_token"):
        await callback.answer(
            "❌ Сессия истекла. Пожалуйста, авторизуйтесь заново.", show_alert=True
        )
        return

    await callback.message.answer(
        "💳 <b>Введите сумму пополнения в гривнах:</b>\n<i>(Например: 100, 250, 500)</i>",
        parse_mode="HTML",
    )
    await state.set_state(TopUpStates.waiting_for_amount)
    await callback.answer()


@router.message(TopUpStates.waiting_for_amount)
async def process_topup_amount(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("❌ Пожалуйста, напишите сумму текстом (числом).")
        return

    amount_text = message.text.strip()

    try:
        amount = float(amount_text)
        if amount <= 0:
            raise ValueError()
    except ValueError:
        await message.answer(
            "❌ Пожалуйста, введите корректную сумму больше нуля (целое число или с точкой)."
        )
        return

    await message.answer("🔄 <i>Генерирую ссылку для оплаты...</i>", parse_mode="HTML")

    try:
        response = await api_client.post(
            "/api/v1/users/me/balance/top-up", state=state, json={"amount": amount}
        )

        if response.status_code == 200:
            payment_data = response.json()
            payment_url = payment_data.get("payment_url")
            transaction_id = payment_data.get("transaction_id")

            # InlineKeyboardMarkup для URL не требует callback_data
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="💳 Оплатить через Stripe", url=payment_url
                        )
                    ]
                ]
            )

            await message.answer(
                f"✅ <b>Ссылка успешно создана!</b>\n\n"
                f"💵 Сумма к оплате: <b>{amount:.2f} ₴</b>\n"
                f"🆔 ID транзакции: <code>{transaction_id}</code>\n\n"
                f"Нажмите кнопку ниже для перехода к безопасной оплате. "
                f"После успешной оплаты баланс обновится автоматически.",
                reply_markup=keyboard,
                parse_mode="HTML",
            )
            # Сбрасываем стейт (токены остаются)
            await state.set_state(None)
        else:
            await message.answer(
                f"❌ Не удалось создать платеж. Сервер вернул код: {response.status_code}"
            )
            await state.set_state(None)

    except Exception as e:
        await message.answer(f"❌ Ошибка при обращении к серверу: {str(e)}")
        await state.set_state(None)
