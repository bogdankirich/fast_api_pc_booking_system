import httpx
from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

router = Router()


@router.message(Command("my_bookings"))
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

                result = "📋 Ваши бронирования:\n\n"
                for booking in bookings:
                    pc_id = booking.get("pc_id")
                    start_time = booking.get("start_time")
                    end_time = booking.get("end_time")
                    status = booking.get("status")
                    total_cost = booking.get("total_cost")

                    result += (
                        f"🖥 ПК #{pc_id}\n"
                        f"⏰ Начало: {start_time}\n"
                        f"⏰ Конец: {end_time}\n"
                        f"📊 Статус: {status}\n"
                        f"💰 Стоимость: {total_cost}\n"
                        f"{'─' * 30}\n"
                    )

                await message.answer(result)

            elif response.status_code == 401:
                await message.answer(
                    "❌ Токен недействителен. Пожалуйста, выполните /login снова."
                )
            else:
                await message.answer(f"❌ Ошибка сервера: {response.status_code}")

        except httpx.RequestError as e:
            await message.answer(f"❌ Ошибка подключения к API: {str(e)}")
