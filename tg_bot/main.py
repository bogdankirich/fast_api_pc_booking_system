import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from tg_bot.handlers import auth, book, bookings, common, profile


async def main():
    logging.basicConfig(level=logging.INFO)

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден в .env")

    redis_client = Redis.from_url("redis://redis:6379/1", decode_responses=True)
    storage = RedisStorage(redis=redis_client)

    bot = Bot(token=token)
    dp = Dispatcher(storage=storage)

    dp.include_router(common.router)
    dp.include_router(auth.router)
    dp.include_router(profile.router)
    dp.include_router(bookings.router)
    dp.include_router(book.router)

    try:
        logging.info("Starting Telegram Bot...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await redis_client.aclose()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
