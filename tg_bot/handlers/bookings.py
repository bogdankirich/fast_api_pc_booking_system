from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from tg_bot.utils.api_client import APIClient

router = Router()
api_client = APIClient()


# --- ФАБРИКА КНОПОК ---
class CancelCallback(CallbackData, prefix="cancel"):
    booking_id: int


@router.message(Command("my_bookings"))
@router.message(F.text == "📅 Мои брони")
async def cmd_my_bookings(message: Message, state: FSMContext):
    user_data = await state.get_data()
    access_token = user_data.get("access_token")

    if not access_token:
        await message.answer("❌ Вы не авторизованы. Сначала выполните команду /login")
        return

    try:
        response = await api_client.get("/api/v1/bookings/", state=state)

        if response.status_code == 200:
            bookings = response.json()

            if not bookings:
                await message.answer("📋 У вас нет активных бронирований.")
                return

            for booking in bookings:
                text = (
                    f"🖥 **ПК #{booking.get('pc_id')}**\n"
                    f"⏰ Начало: {booking.get('start_time')}\n"
                    f"⏰ Конец: {booking.get('end_time')}\n"
                    f"📊 Статус: {booking.get('status')}\n"
                    f"💰 Стоимость: {booking.get('total_cost')} ₴"
                )

                # Используем Builder и строгую типизацию кнопок
                builder = InlineKeyboardBuilder()
                builder.button(
                    text="❌ Отменить бронь",
                    callback_data=CancelCallback(booking_id=booking.get("id")),
                )

                await message.answer(
                    text, reply_markup=builder.as_markup(), parse_mode="Markdown"
                )
        else:
            await message.answer(f"❌ Ошибка сервера: {response.status_code}")

    except Exception as e:
        await message.answer(f"❌ Ошибка: {str(e)}")


@router.callback_query(CancelCallback.filter())
async def cancel_booking(
    callback: CallbackQuery, callback_data: CancelCallback, state: FSMContext
):
    # Страховка для линтера
    if not isinstance(callback.message, Message):
        return

    user_data = await state.get_data()
    access_token = user_data.get("access_token")

    if not access_token:
        await callback.answer("❌ Токен отсутствует", show_alert=True)
        return

    try:
        # Используем ID прямо из распакованной кнопки
        response = await api_client.delete(
            f"/api/v1/bookings/{callback_data.booking_id}", state=state
        )

        if response.status_code in (204, 200):
            original_text = callback.message.text or "Бронь"
            # Убираем кнопку отмены, чтобы нельзя было нажать дважды
            await callback.message.edit_text(
                f"{original_text}\n\n❌ **Бронь отменена**", parse_mode="Markdown"
            )
            await callback.answer("Успешно отменено")

        elif response.status_code == 403:
            await callback.answer(
                "❌ У вас нет прав на отмену этой брони", show_alert=True
            )
        elif response.status_code == 404:
            await callback.answer("❌ Бронь не найдена", show_alert=True)
        else:
            error_detail = response.json().get("detail", "Неизвестная ошибка")
            await callback.answer(f"❌ Ошибка: {error_detail}", show_alert=True)

    except Exception as e:
        await callback.answer(f"❌ Ошибка подключения: {str(e)}", show_alert=True)
