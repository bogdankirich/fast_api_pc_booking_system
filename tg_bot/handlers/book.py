from datetime import datetime, timezone

import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from tg_bot.keyboards import get_main_menu

router = Router()


class BookStates(StatesGroup):
    waiting_for_zone = State()
    waiting_for_time = State()
    waiting_for_pc = State()


@router.message(Command("book"))
@router.message(F.text == "🖥 Забронировать ПК")
@router.callback_query(F.data == "start_booking")  #
async def cmd_book(event: Message | CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    access_token = user_data.get("access_token")

    message = event if isinstance(event, Message) else event.message

    if not isinstance(message, Message):
        return

    if not access_token:
        if isinstance(event, CallbackQuery):
            await event.answer("❌ Вы не авторизованы!", show_alert=True)
        else:
            await message.answer(
                "❌ Вы не авторизованы. Сначала выполните команду /login"
            )
        return

    if isinstance(event, CallbackQuery):
        await event.answer()

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "http://web:8000/api/v1/zones/",
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                zones = response.json()

                if not zones:
                    await message.answer("❌ Нет доступных зон.")
                    return

                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=zone["name"],
                                callback_data=f"book_zone_{zone['id']}",
                            )
                        ]
                        for zone in zones
                    ]
                )

                await message.answer("Выберите зону:", reply_markup=keyboard)
                await state.set_state(BookStates.waiting_for_zone)

            elif response.status_code == 401:
                await message.answer(
                    "❌ Токен недействителен. Пожалуйста, выполните /login снова."
                )
            else:
                await message.answer(f"❌ Ошибка сервера: {response.status_code}")

        except httpx.RequestError as e:
            await message.answer(f"❌ Ошибка подключения к API: {str(e)}")


@router.callback_query(BookStates.waiting_for_zone, F.data.startswith("book_zone_"))
async def process_zone_selection(callback: CallbackQuery, state: FSMContext):
    if callback.data is None or callback.message is None:
        await callback.answer("Ошибка: данные не получены")
        return

    zone_id = int(callback.data.split("_")[2])
    await state.update_data(zone_id=zone_id)

    await callback.message.answer(
        "Введите время бронирования на сегодня в формате ЧЧ:ММ ЧЧ:ММ\n"
        "Например: 14:00 16:00"
    )
    await state.set_state(BookStates.waiting_for_time)
    await callback.answer()


@router.message(BookStates.waiting_for_time)
async def process_time(message: Message, state: FSMContext):
    if message.text is None:
        await message.answer("❌ Ошибка: текст сообщения не получен.")
        return

    user_data = await state.get_data()
    access_token = user_data.get("access_token")
    zone_id = user_data.get("zone_id")

    if not access_token:
        await message.answer("❌ Токен отсутствует. Выполните /login снова.")
        await state.clear()
        return

    try:
        times = message.text.strip().split()
        if len(times) != 2:
            await message.answer(
                "❌ Неверный формат. Используйте: ЧЧ:ММ ЧЧ:ММ (например, 14:00 16:00)"
            )
            return

        start_hour, start_minute = map(int, times[0].split(":"))
        end_hour, end_minute = map(int, times[1].split(":"))

        now = datetime.now(timezone.utc)
        start_time = now.replace(
            hour=start_hour, minute=start_minute, second=0, microsecond=0
        )
        end_time = now.replace(
            hour=end_hour, minute=end_minute, second=0, microsecond=0
        )

        start_time_iso = start_time.isoformat()
        end_time_iso = end_time.isoformat()

        await state.update_data(start_time=start_time_iso, end_time=end_time_iso)

    except (ValueError, IndexError):
        await message.answer(
            "❌ Неверный формат времени. Используйте: ЧЧ:ММ ЧЧ:ММ (например, 14:00 16:00)"
        )
        return

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "http://web:8000/api/v1/pcs/available",
                params={
                    "zone_id": zone_id,
                    "start_time": start_time_iso,
                    "end_time": end_time_iso,
                },
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 200:
                pcs = response.json()

                if not pcs:
                    await message.answer(
                        "❌ В этой зоне нет свободных ПК на это время.\n"
                        "Введите другое время в формате ЧЧ:ММ ЧЧ:ММ или начните заново с /book"
                    )
                    return

                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=f"ПК #{pc['id']}",
                                callback_data=f"book_pc_{pc['id']}",
                            )
                        ]
                        for pc in pcs
                    ]
                )

                await message.answer("Выберите ПК:", reply_markup=keyboard)
                await state.set_state(BookStates.waiting_for_pc)

            elif response.status_code == 401:
                await message.answer(
                    "❌ Токен недействителен. Пожалуйста, выполните /login снова."
                )
                await state.clear()
            else:
                error_detail = response.json().get("detail", "Неизвестная ошибка")
                await message.answer(
                    f"❌ Ошибка: {error_detail}\n\n"
                    "Попробуйте ввести другое время в формате ЧЧ:ММ ЧЧ:ММ"
                )
                return

        except httpx.RequestError as e:
            await message.answer(
                f"❌ Ошибка подключения к API: {str(e)}\n\n"
                "Попробуйте ввести время снова или начните заново с /book"
            )
            return


@router.callback_query(BookStates.waiting_for_pc, F.data.startswith("book_pc_"))
async def process_pc_selection(callback: CallbackQuery, state: FSMContext):
    if callback.data is None or callback.message is None:
        await callback.answer("Ошибка: данные не получены")
        return

    pc_id = int(callback.data.split("_")[2])
    user_data = await state.get_data()
    access_token = user_data.get("access_token")
    refresh_token = user_data.get("refresh_token")
    start_time = user_data.get("start_time")
    end_time = user_data.get("end_time")

    if not access_token or not start_time or not end_time:
        await callback.message.answer("❌ Ошибка: данные сессии потеряны.")
        await state.clear()
        await callback.answer()
        return

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://web:8000/api/v1/bookings/",
                json={"pc_id": pc_id, "start_time": start_time, "end_time": end_time},
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=10.0,
            )

            if response.status_code == 201:
                booking = response.json()
                await callback.message.answer(
                    f"✅ Бронь успешно создана!\n\n"
                    f"🖥 ПК #{booking['pc_id']}\n"
                    f"⏰ Начало: {booking['start_time']}\n"
                    f"⏰ Конец: {booking['end_time']}\n"
                    f"💰 Стоимость: {booking['total_cost']}",
                    reply_markup=get_main_menu(),
                )
            elif response.status_code == 401:
                await callback.message.answer(
                    "❌ Токен недействителен. Пожалуйста, выполните /login снова."
                )
            else:
                error_detail = response.json().get("detail", "Неизвестная ошибка")
                await callback.message.answer(
                    f"❌ Ошибка при создании брони: {error_detail}"
                )

        except httpx.RequestError as e:
            await callback.message.answer(f"❌ Ошибка подключения к API: {str(e)}")

    await state.clear()
    await state.update_data(access_token=access_token, refresh_token=refresh_token)
    await callback.answer()
