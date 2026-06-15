import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from tg_bot.keyboards import get_main_menu
from tg_bot.utils.api_client import APIClient

router = Router()
api_client = APIClient(base_url="http://web:8000")


class BookStates(StatesGroup):
    choosing_zone = State()
    choosing_date = State()
    choosing_time = State()  # Выбор начала
    choosing_duration = State()  # Выбор продолжительности
    choosing_pc = State()


class BookCallback(CallbackData, prefix="book", sep="|"):
    step: str
    zone_id: int | None = None
    date_str: str | None = None
    time_str: str | None = None  # Например "14:00"
    duration: float | None = None  # В часах
    pc_id: int | None = None


@router.message(Command("book"))
@router.message(F.text == "🖥 Забронировать ПК")
@router.callback_query(F.data == "start_booking")
@router.callback_query(
    BookCallback.filter(F.step == "back_to_zones")
)  # Ловим кнопку НАЗАД
async def cmd_book(event: Message | CallbackQuery, state: FSMContext):
    # Если это коллбек (кнопка "назад"), отвечаем серверу, чтобы не висели часики
    if isinstance(event, CallbackQuery):
        await event.answer()
        # СТРАХОВКА ДЛЯ ЛИНТЕРА:
        if not isinstance(event.message, Message):
            return
        message = event.message
    else:
        message = event

    try:
        # Твой APIClient сам подставит токен из state и обновит его, если нужно!
        response = await api_client.get("/api/v1/zones/", state=state)

        if response.status_code == 200:
            zones = response.json()
            if not zones:
                await message.answer("❌ Нет доступных зон.")
                return

            # Строим клавиатуру через Builder
            builder = InlineKeyboardBuilder()
            for zone in zones:
                # Генерируем красивую Type-Safe кнопку
                builder.button(
                    text=zone["name"],
                    callback_data=BookCallback(step="zone", zone_id=zone["id"]),
                )
            builder.adjust(1)  # По одной кнопке в ряд

            text = "📍 Выберите зону:"
            if isinstance(event, CallbackQuery):
                # Редактируем старое сообщение, чтобы не спамить в чат
                await message.edit_text(text, reply_markup=builder.as_markup())
            else:
                await message.answer(text, reply_markup=builder.as_markup())

            await state.set_state(BookStates.choosing_zone)

    except ValueError:
        # Эту ошибку кидает твой APIClient, если нет токена
        await message.answer("❌ Вы не авторизованы. Сначала выполните /login")
    except Exception as e:
        await message.answer(f"❌ Ошибка подключения: {str(e)}")


# Обрати внимание, как изящно мы ловим нужный коллбек через фильтр!
@router.callback_query(BookCallback.filter(F.step == "zone"))
@router.callback_query(
    BookCallback.filter(F.step == "back_to_dates")
)  # Для возврата назад
async def process_zone_selection(
    callback: CallbackQuery,
    callback_data: BookCallback,  # Aiogram сам распакует данные из кнопки сюда!
    state: FSMContext,
):
    # Если мы идем вперед, сохраняем zone_id. Если возвращаемся назад, берем из state
    if not isinstance(callback.message, Message):
        await callback.answer("Ошибка: сообщение недоступно", show_alert=True)
        return

    if callback_data.step == "zone":
        await state.update_data(zone_id=callback_data.zone_id)

    await callback.answer()

    # Генерируем кнопки на 5 дней вперед
    builder = InlineKeyboardBuilder()
    now = datetime.now()  # Тут можно использовать pytz для Киева

    for i in range(5):
        target_date = now + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")

        # Красивые названия дней
        if i == 0:
            btn_text = "📅 Сегодня"
        elif i == 1:
            btn_text = "📅 Завтра"
        else:
            btn_text = target_date.strftime("%d.%m.%Y")

        builder.button(
            text=btn_text, callback_data=BookCallback(step="date", date_str=date_str)
        )

    # ДОБАВЛЯЕМ КНОПКУ "НАЗАД"
    builder.button(
        text="🔙 Назад к зонам", callback_data=BookCallback(step="back_to_zones")
    )
    builder.adjust(1)  # По одной в ряд

    await callback.message.edit_text(
        "📅 Выберите дату бронирования:", reply_markup=builder.as_markup()
    )
    await state.set_state(BookStates.choosing_date)


@router.callback_query(BookCallback.filter(F.step == "date"))
async def process_date_selection(
    callback: CallbackQuery, callback_data: BookCallback, state: FSMContext
):
    if not isinstance(callback.message, Message):
        return

    # Сохраняем выбранную дату
    await state.update_data(date_str=callback_data.date_str)

    # Генерируем сетку времени с 10:00 до 22:00
    builder = InlineKeyboardBuilder()
    for hour in range(10, 23):
        time_str = f"{hour:02d}:00"
        builder.button(
            text=time_str, callback_data=BookCallback(step="time", time_str=time_str)
        )

    # Делаем сетку 4 кнопки в ряд
    builder.adjust(4)

    # Кнопка назад к выбору даты
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад к датам",
            callback_data=BookCallback(step="back_to_dates").pack(),
        )
    )

    await callback.message.edit_text(
        f"📅 Выбрана дата: {callback_data.date_str}\n\n"
        f"⏰ Выберите время начала на клавиатуре\n"
        f"⌨️ Или **напишите точное время вручную** (например, 14:15):",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
    await state.set_state(BookStates.choosing_time)


# --- НАВИГАЦИОННЫЕ КНОПКИ "НАЗАД" ---


@router.callback_query(BookCallback.filter(F.step == "back_to_dates"))
async def go_back_to_dates(callback: CallbackQuery, state: FSMContext):
    # СТРАХОВКА ДЛЯ ЛИНТЕРА
    if not isinstance(callback.message, Message):
        return

    # Генерируем календарь заново
    builder = InlineKeyboardBuilder()
    now = datetime.now()
    for i in range(5):
        target_date = now + timedelta(days=i)
        date_str = target_date.strftime("%Y-%m-%d")
        btn_text = (
            "📅 Сегодня"
            if i == 0
            else "📅 Завтра"
            if i == 1
            else target_date.strftime("%d.%m.%Y")
        )
        builder.button(
            text=btn_text, callback_data=BookCallback(step="date", date_str=date_str)
        )

    builder.button(
        text="🔙 Назад к зонам", callback_data=BookCallback(step="back_to_zones")
    )
    builder.adjust(1)

    await callback.message.edit_text(
        "📅 Выберите дату бронирования:", reply_markup=builder.as_markup()
    )
    await state.set_state(BookStates.choosing_date)
    await callback.answer()


@router.callback_query(BookCallback.filter(F.step == "back_to_time"))
async def go_back_to_time(callback: CallbackQuery, state: FSMContext):
    # СТРАХОВКА ДЛЯ ЛИНТЕРА
    if not isinstance(callback.message, Message):
        return

    user_data = await state.get_data()
    date_str = user_data.get("date_str")

    if not date_str:
        await callback.answer("Ошибка сессии", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for hour in range(10, 23):
        time_str = f"{hour:02d}:00"
        builder.button(
            text=time_str, callback_data=BookCallback(step="time", time_str=time_str)
        )

    builder.adjust(4)
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад к датам",
            callback_data=BookCallback(step="back_to_dates").pack(),
        )
    )

    await callback.message.edit_text(
        f"📅 Выбрана дата: {date_str}\n\n"
        f"⏰ Выберите время начала на клавиатуре\n"
        f"⌨️ Или напишите точное время вручную:",
        reply_markup=builder.as_markup(),
    )
    await state.set_state(BookStates.choosing_time)
    await callback.answer()


@router.callback_query(BookCallback.filter(F.step == "time"))
async def process_time_button(
    callback: CallbackQuery, callback_data: BookCallback, state: FSMContext
):
    if not isinstance(callback.message, Message):
        return

    # СТРАХОВКА ДЛЯ ЛИНТЕРА: доказываем, что time_str точно есть
    if not callback_data.time_str:
        await callback.answer("Ошибка: время не выбрано", show_alert=True)
        return

    await state.update_data(time_str=callback_data.time_str)
    await callback.answer()

    # Теперь линтер спокоен, так как callback_data.time_str 100% строка
    await ask_for_duration(callback.message, callback_data.time_str, state)


# ХЭНДЛЕР Б: Ловит текст, если юзер решил написать "14:15" руками
@router.message(BookStates.choosing_time, F.text)
async def process_time_text(message: Message, state: FSMContext):
    if not message.text:
        await message.answer(
            "❌ Пожалуйста, отправьте время текстом (например, 14:15)."
        )
        return

    text = message.text.strip()

    # Простая регулярка для проверки формата ЧЧ:ММ (допускаем точку или двоеточие)
    match = re.match(r"^([0-1]?[0-9]|2[0-3])[:.]([0-5][0-9])$", text)

    if not match:
        await message.answer(
            "❌ Неверный формат. Пожалуйста, используйте формат ЧЧ:ММ (например, 14:15)\n"
            "Или выберите время на кнопках выше."
        )
        return

    # Форматируем красиво, даже если юзер ввел "9:5" -> "09:05"
    hours, minutes = match.groups()
    time_str = f"{int(hours):02d}:{int(minutes):02d}"

    await state.update_data(time_str=time_str)

    # Переводим к следующему шагу
    await ask_for_duration(message, time_str, state)


@router.message(BookStates.choosing_duration, F.text)
async def process_duration_text(message: Message, state: FSMContext):
    if not message.text:
        return

    text = message.text.strip()
    user_data = await state.get_data()
    start_time_str = user_data.get("time_str")

    # СТРАХОВКА ДЛЯ ЛИНТЕРА (Решает ошибку с strptime)
    if not isinstance(start_time_str, str):
        await message.answer(
            "❌ Ошибка сессии: время начала потеряно. Начните заново с /book."
        )
        return

    duration_hours = None

    # Вариант А: Юзер ввел просто цифру (часы) - "2", "3.5"
    if text.replace(".", "", 1).isdigit():
        duration_hours = float(text)

    # Вариант Б: Юзер ввел точное конечное время
    else:
        import re

        match = re.match(r"^([0-1]?[0-9]|2[0-3])[:.]([0-5][0-9])$", text)
        if match:
            hours, minutes = match.groups()
            end_time_str = f"{int(hours):02d}:{int(minutes):02d}"

            fmt = "%H:%M"
            t1 = datetime.strptime(start_time_str, fmt)
            t2 = datetime.strptime(end_time_str, fmt)

            if t2 <= t1:
                t2 += timedelta(days=1)

            duration_hours = (t2 - t1).total_seconds() / 3600
        else:
            await message.answer(
                "❌ Введите количество часов (например, 2) или точное время (например, 16:30)."
            )
            return

    await state.update_data(temp_duration=duration_hours)
    await process_duration_selection(message, state)


# ОБЩАЯ ФУНКЦИЯ: Чтобы не дублировать код для шага выбора часов
async def ask_for_duration(message: Message, time_str: str, state: FSMContext):
    builder = InlineKeyboardBuilder()

    # Генерируем кнопки от 1 до 5 часов
    for hours in range(1, 6):
        builder.button(
            text=f"{hours} час(ов)",
            callback_data=BookCallback(step="duration", duration=hours),
        )

    builder.button(
        text="Пакет НОЧЬ", callback_data=BookCallback(step="duration", duration=10)
    )
    builder.adjust(2)  # По 2 кнопки в ряд

    # Кнопка НАЗАД (возвращает к календарю)
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад ко времени",
            callback_data=BookCallback(step="back_to_time").pack(),
        )
    )

    await message.answer(
        f"✅ Начало сеанса: **{time_str}**.\n\n⏳ На сколько часов бронируем ПК?",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
    await state.set_state(BookStates.choosing_duration)


@router.callback_query(BookCallback.filter(F.step == "duration"))
async def process_duration_selection(
    event: CallbackQuery | Message,
    state: FSMContext,
    callback_data: BookCallback | None = None,  # <-- Исправлено для линтера
):
    # Определяем, откуда пришли данные
    if isinstance(event, CallbackQuery):
        await event.answer()
        message = event.message
        duration = callback_data.duration if callback_data else None
    else:
        message = event
        user_data = await state.get_data()
        duration = user_data.get("temp_duration")

    if not isinstance(message, Message) or not duration:
        return

    # Достаем все собранные данные
    user_data = await state.get_data()
    zone_id = user_data.get("zone_id")
    date_str = user_data.get("date_str")
    time_str = user_data.get("time_str")

    if not date_str or not time_str:
        await message.answer("❌ Данные потеряны. Начните заново с /book")
        return

    # Склеиваем дату и время
    kiev_tz = ZoneInfo("Europe/Kyiv")
    local_start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(
        tzinfo=kiev_tz
    )
    utc_start = local_start.astimezone(ZoneInfo("UTC"))

    if local_start < datetime.now(kiev_tz):
        error_msg = (
            "❌ Выбранное время уже прошло!\nПожалуйста, выберите время в будущем."
        )

        back_btn = InlineKeyboardButton(
            text="🔙 Назад ко времени",
            callback_data=BookCallback(step="back_to_time").pack(),
        )
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_btn]])

        if isinstance(event, CallbackQuery):
            await message.edit_text(error_msg, reply_markup=keyboard)
        else:
            await message.answer(error_msg, reply_markup=keyboard)
        return

    # Явно кастуем duration в float (решает ошибку timedelta)
    utc_end = utc_start + timedelta(hours=float(duration))

    start_iso = utc_start.isoformat()
    end_iso = utc_end.isoformat()

    await state.update_data(start_time=start_iso, end_time=end_iso, duration=duration)

    # Идем в API за свободными ПК
    try:
        response = await api_client.get(
            "/api/v1/pcs/available",
            params={
                "zone_id": zone_id,
                "start_time": start_iso,
                "end_time": end_iso,
            },
            state=state,
        )

        if response.status_code == 200:
            pcs = response.json()

            if not pcs:
                back_btn = InlineKeyboardButton(
                    text="🔙 Назад ко времени",
                    callback_data=BookCallback(step="back_to_time").pack(),
                )
                keyboard = InlineKeyboardMarkup(inline_keyboard=[[back_btn]])

                text_error = "😔 К сожалению, на это время нет свободных ПК.\nПопробуйте выбрать другое время или зону."

                # Универсальная отправка
                if isinstance(event, CallbackQuery):
                    await message.edit_text(text_error, reply_markup=keyboard)
                else:
                    await message.answer(text_error, reply_markup=keyboard)
                return

            # Строим кнопки с доступными компами
            builder = InlineKeyboardBuilder()
            for pc in pcs:
                builder.button(
                    text=f"🖥 ПК #{pc['id']}",
                    callback_data=BookCallback(step="pc", pc_id=pc["id"]),
                )

            builder.adjust(3)
            builder.row(
                InlineKeyboardButton(
                    text="🔙 Назад ко времени",
                    callback_data=BookCallback(step="back_to_time").pack(),
                )
            )

            text_success = f"✅ Найдено {len(pcs)} свободных ПК.\nВыберите тот, который вам нравится:"

            # Универсальная отправка
            if isinstance(event, CallbackQuery):
                await message.edit_text(text_success, reply_markup=builder.as_markup())
            else:
                await message.answer(text_success, reply_markup=builder.as_markup())

            await state.set_state(BookStates.choosing_pc)

        elif response.status_code == 401:
            await message.answer("❌ Токен устарел. Введите /login")
        else:
            await message.answer("❌ Ошибка при поиске ПК.")

    except Exception as e:
        await message.answer(f"❌ Ошибка подключения: {str(e)}")


@router.callback_query(BookCallback.filter(F.step == "pc"))
async def process_pc_preview(
    callback: CallbackQuery, callback_data: BookCallback, state: FSMContext
):
    if not isinstance(callback.message, Message) or not callback_data.pc_id:
        return

    # Сохраняем выбранный ПК
    await state.update_data(pc_id=callback_data.pc_id)
    user_data = await state.get_data()

    zone_id = user_data.get("zone_id")
    duration = user_data.get("duration")  # Мы добавили это сохранение в шаге 1

    # Быстро запрашиваем тариф зоны, чтобы показать сумму до списания!
    total_cost_str = "по тарифу"
    if duration:
        try:
            zones_resp = await api_client.get("/api/v1/zones/", state=state)
            if zones_resp.status_code == 200:
                current_zone = next(
                    (z for z in zones_resp.json() if z["id"] == zone_id), None
                )
                if current_zone:
                    cost = float(duration) * float(current_zone["hourly_rate"])
                    total_cost_str = f"{cost:.2f} ₴"
        except Exception:
            pass  # Если не получилось, оставим "по тарифу"

    builder = InlineKeyboardBuilder()
    # Вот она, кнопка реального списания!
    builder.button(
        text="✅ Подтвердить и забронировать",
        callback_data=BookCallback(step="confirm"),
    )
    builder.button(text="🔙 Отменить", callback_data=BookCallback(step="back_to_time"))
    builder.adjust(1)

    await callback.message.edit_text(
        f"🧾 **ПРЕДВАРИТЕЛЬНЫЙ ЧЕК**\n\n"
        f"🖥 **ПК:** #{callback_data.pc_id}\n"
        f"📅 **Дата:** {user_data.get('date_str')}\n"
        f"⏰ **Время:** {user_data.get('time_str')} (на {duration} ч.)\n"
        f"💰 **К списанию:** {total_cost_str}\n\n"
        f"Нажмите подтвердить для создания брони.",
        reply_markup=builder.as_markup(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(BookCallback.filter(F.step == "confirm"))
async def process_booking_confirmation(callback: CallbackQuery, state: FSMContext):
    if not isinstance(callback.message, Message):
        return

    await callback.answer("⏳ Создаем бронь...", show_alert=False)

    user_data = await state.get_data()
    pc_id = user_data.get("pc_id")
    start_time = user_data.get("start_time")
    end_time = user_data.get("end_time")

    try:
        response = await api_client.post(
            "/api/v1/bookings/",
            json={"pc_id": pc_id, "start_time": start_time, "end_time": end_time},
            state=state,
        )

        if response.status_code == 201:
            booking = response.json()

            kiev_tz = ZoneInfo("Europe/Kyiv")
            local_start = (
                datetime.fromisoformat(booking["start_time"])
                .astimezone(kiev_tz)
                .strftime("%H:%M")
            )
            local_end = (
                datetime.fromisoformat(booking["end_time"])
                .astimezone(kiev_tz)
                .strftime("%H:%M")
            )

            await callback.message.delete()
            await callback.message.answer(
                f"🎉 **Бронь успешно создана!**\n\n"
                f"🖥 **ПК:** #{booking['pc_id']}\n"
                f"⏰ **Время:** {local_start} - {local_end}\n"
                f"💰 **Списано:** {booking['total_cost']} ₴\n\n"
                f"Ждем вас в клубе!",
                reply_markup=get_main_menu(),
                parse_mode="Markdown",
            )

            acc_token = user_data.get("access_token")
            ref_token = user_data.get("refresh_token")
            await state.clear()
            await state.update_data(access_token=acc_token, refresh_token=ref_token)

        else:
            error_data = response.json()
            msg = error_data.get("detail", "Неизвестная ошибка")
            if isinstance(msg, list):
                msg = msg[0].get("msg", "Ошибка валидации")
            await callback.message.answer(f"❌ Ошибка бронирования: {msg}")

    except Exception as e:
        await callback.message.answer(f"❌ Ошибка подключения: {str(e)}")
