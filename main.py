# -*- coding: utf-8 -*-
"""
Точка входа: запуск бота для управления отзывами (Яндекс Карты / 2ГИС).
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
from database import init_db
from middlewares import DbSessionMiddleware, AdminOnlyMiddleware
from handlers import user_router, admin_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main() -> None:
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не задан. Создайте файл .env по образцу .env.example")
        return

    # Папка для SQLite - ИСПРАВЛЕНО: используем BASE_DIR из config
    from config import BASE_DIR
    if "sqlite" in os.environ.get("DATABASE_URL", ""):
        os.makedirs(os.path.join(BASE_DIR, "data"), exist_ok=True)

    await init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Сессия БД для всех хендлеров
    dp.update.middleware(DbSessionMiddleware())

    dp.include_router(user_router)

    # Админ-роутер: только для пользователей из ADMIN_IDS - ИСПРАВЛЕНО для aiogram 3.x
    # Вместо outer_middleware используем middleware для конкретных типов обновлений
    admin_router.message.middleware(AdminOnlyMiddleware())
    admin_router.callback_query.middleware(AdminOnlyMiddleware())

    dp.include_router(admin_router)

    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())