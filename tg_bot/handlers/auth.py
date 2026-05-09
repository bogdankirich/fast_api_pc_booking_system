import httpx
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from tg_bot.keyboards import get_main_menu, get_start_menu

router = Router()


class LoginStates(StatesGroup):
    waiting_for_email = State()
    waiting_for_password = State()


@router.message(Command("login"))
@router.message(F.text == "🔑 Войти")
async def cmd_login(message: Message, state: FSMContext):
    await message.answer("Введите ваш email:")
    await state.set_state(LoginStates.waiting_for_email)


@router.message(LoginStates.waiting_for_email, F.text)
async def process_email(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, отправьте email текстом.")
        return
    email = message.text.strip()
    await state.update_data(email=email)
    await message.answer("Введите ваш пароль:")
    await state.set_state(LoginStates.waiting_for_password)


@router.message(LoginStates.waiting_for_password, F.text)
async def process_password(message: Message, state: FSMContext):
    if not message.text:
        await message.answer("Пожалуйста, отправьте пароль текстом.")
        return
    password = message.text.strip()
    user_data = await state.get_data()
    email = user_data.get("email")

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://web:8000/api/v1/login",
                data={"username": email, "password": password},
                timeout=10.0,
            )

            if response.status_code == 200:
                token_data = response.json()
                access_token = token_data.get("access_token")
                refresh_token = token_data.get("refresh_token")

                await state.clear()
                await state.update_data(
                    access_token=access_token,
                    refresh_token=refresh_token,
                )
                await message.answer(
                    "✅ Вы успешно вошли!", reply_markup=get_main_menu()
                )
            elif response.status_code in (401, 400):
                error_detail = response.json().get(
                    "detail", "Неверный email или пароль"
                )
                await message.answer(
                    f"❌ Ошибка: {error_detail}", reply_markup=get_start_menu()
                )
                await state.clear()
            else:
                await message.answer(
                    f"❌ Ошибка сервера: {response.status_code}",
                    reply_markup=get_start_menu(),
                )
                await state.clear()

        except httpx.RequestError as e:
            await message.answer(
                f"❌ Ошибка подключения к API: {str(e)}",
                reply_markup=get_start_menu(),
            )
            await state.clear()
