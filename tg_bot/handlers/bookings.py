import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

router = Router()


@router.message(Command("my_bookings"))
@router.message(F.text == "📅 Мои брони")
async def cmd_my_bookings(message: Message, state: FSMContext):
    user_data = await state.get_data()
    access_token = user_data.get("access_token")

    if not access_token:
        await message.answer(
            "❌ Вы не авторизованы. Сначала выполните команду /login"
        )
        return

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "http://web:8000/api/v1/bookings/",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                bookings = response.json()

                if not bookings:
                    await message.answer("📋 У вас нет активных бронирований.")
                    return

                for booking in bookings:
                    booking_id = booking.get("id")
                    pc_id = booking.get("pc_id")
                    start_time = booking.get("start_time")
                    end_time = booking.get("end_time")
                    status = booking.get("status")
                    total_cost = booking.get("total_cost")

                    text = (
                        f"🖥 ПК #{pc_id}\n"
                        f"⏰ Начало: {start_time}\n"
                        f"⏰ Конец: {end_time}\n"
                        f"📊 Статус: {status}\n"
                        f"💰 Стоимость: {total_cost}"
                    )

                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="❌ Отменить бронь",
                                    callback_data=f"cancel_booking_{booking_id}",
                                )
                            ]
                        ]
                    )

                    await message.answer(text, reply_markup=keyboard)

            elif response.status_code == 401:
                await message.answer(
                    "❌ Токен недействителен. Пожалуйста, выполните /login снова."
                )
            else:
                await message.answer(f"❌ Ошибка сервера: {response.status_code}")

        except httpx.RequestError as e:
            await message.answer(f"❌ Ошибка подключения к API: {str(e)}")


@router.callback_query(F.data.startswith("cancel_booking_"))
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    if callback.data is None or callback.message is None:
        await callback.answer("Ошибка: данные не получены")
        return

    booking_id = int(callback.data.split("_")[2])
    user_data = await state.get_data()
    access_token = user_data.get("access_token")

    if not access_token:
        await callback.answer("❌ Токен отсутствует", show_alert=True)
        return

    async with httpx.AsyncClient() as client:
        try:
            response = await client.delete(
                f"http://web:8000/api/v1/bookings/{booking_id}",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code in (204, 200):
                await callback.message.edit_text(
                    f"{callback.message.text}\n\n❌ Бронь отменена"
                )
                await callback.answer("Успешно отменено")
            elif response.status_code == 401:
                await callback.answer(
                    "❌ Токен недействителен. Выполните /login снова", show_alert=True
                )
            elif response.status_code == 403:
                await callback.answer(
                    "❌ У вас нет прав на отмену этой брони", show_alert=True
                )
            elif response.status_code == 404:
                await callback.answer("❌ Бронь не найдена", show_alert=True)
            else:
                error_detail = response.json().get("detail", "Неизвестная ошибка")
                await callback.answer(f"❌ Ошибка: {error_detail}", show_alert=True)

        except httpx.RequestError as e:
            await callback.answer(f"❌ Ошибка подключения: {str(e)}", show_alert=True)
