# -*- coding: utf-8 -*-
"""
Точка входа: запуск бота для управления отзывами (Яндекс Карты / 2ГИС).
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, PROXY_URL
from database import init_db
from middlewares import (
    AdminOnlyMiddleware,
    AdminOrManagerMiddleware,
    BlockedUserMiddleware,
    DbSessionMiddleware,
    ManagerOnlyMiddleware,
)
from handlers import admin_router, manager_router, staff_settings_router, user_router
from services.review_scheduler import start_scheduler

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
    # Если сеть требует прокси — укажите PROXY_URL в .env (пример: http://127.0.0.1:10809)
    if PROXY_URL:
        logger.info("Используется прокси: %s", PROXY_URL)
    else:
        logger.warning("PROXY_URL не задан. Подключение идёт напрямую (возможен SSL error).")
    session = AiohttpSession(proxy=PROXY_URL or None)
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher(storage=MemoryStorage())

    # Сессия БД для всех хендлеров
    dp.update.middleware(DbSessionMiddleware())

    dp.include_router(user_router)
    # Если пользователь заблокирован — не даём выполнять действия
    user_router.message.middleware(BlockedUserMiddleware())
    user_router.callback_query.middleware(BlockedUserMiddleware())

    # Менеджер: /manager и callback'и mgr:*
    manager_router.message.middleware(BlockedUserMiddleware())
    manager_router.callback_query.middleware(BlockedUserMiddleware())
    manager_router.message.middleware(ManagerOnlyMiddleware())
    manager_router.callback_query.middleware(ManagerOnlyMiddleware())
    dp.include_router(manager_router)

    # Команды set_welcome / set_help / set_min_* — и у админа, и у менеджера
    staff_settings_router.message.middleware(BlockedUserMiddleware())
    staff_settings_router.message.middleware(AdminOrManagerMiddleware())
    dp.include_router(staff_settings_router)

    # Админ-роутер: только ADMIN_IDS
    admin_router.message.middleware(AdminOnlyMiddleware())
    admin_router.callback_query.middleware(AdminOnlyMiddleware())
    dp.include_router(admin_router)
    scheduler = start_scheduler(bot)

    try:
        logger.info("Бот запущен")
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())