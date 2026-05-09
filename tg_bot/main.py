import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from tg_bot.handlers import auth, bookings, common


async def main():
    logging.basicConfig(level=logging.INFO)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env")

    bot = Bot(token=token)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    dp.include_router(common.router)
    dp.include_router(auth.router)
    dp.include_router(bookings.router)

    logging.info("Starting Telegram Bot...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
