# -*- coding: utf-8 -*-
"""
Точка входа: запуск бота для управления отзывами (Яндекс Карты / 2ГИС).
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN, PROXY_URL, DATABASE_URL, sqlite_db_file_path_from_url
from database import init_db
from middlewares import (
    AdminOnlyMiddleware,
    AdminOrManagerMiddleware,
    BlockedUserMiddleware,
    DbSessionMiddleware,
    ManagerOnlyMiddleware,
    RulesAcceptanceMiddleware,
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

    # Поднимаем папку под SQLite, исходя из реального DATABASE_URL.
    # Это исправляет падение на VPS/Netlify, когда DATABASE_URL не задан в env,
    # но используется значение по умолчанию.
    db_file_path = sqlite_db_file_path_from_url(DATABASE_URL)
    if db_file_path:
        db_dir = os.path.dirname(db_file_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

    await init_db()
    # Если сеть требует прокси — укажите PROXY_URL в .env (пример: http://127.0.0.1:10809)
    if PROXY_URL:
        logger.info("Используется прокси: %s", PROXY_URL)
    else:
        logger.warning("PROXY_URL не задан. Подключение идёт напрямую (возможен SSL error).")
    session = AiohttpSession(proxy=PROXY_URL or None)
    bot = Bot(token=BOT_TOKEN, session=session)
    dp = Dispatcher(storage=MemoryStorage())

    # Show slash-command "micro menu" in Telegram UI.
    # (Appears on typing "/" and is the same as main menu actions.)
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="Перезапустить бота"),
                BotCommand(command="menu", description="Вернуться в главное меню"),
                BotCommand(command="help", description="Инструкция и помощь"),
            ]
        )
    except Exception:
        # If Telegram rejects command registration (or in restricted environments), bot still works.
        logger.exception("Failed to set bot commands")

    # Сессия БД для всех хендлеров
    dp.update.middleware(DbSessionMiddleware())

    dp.include_router(user_router)
    # Если пользователь заблокирован — не даём выполнять действия
    user_router.message.middleware(BlockedUserMiddleware())
    user_router.callback_query.middleware(BlockedUserMiddleware())
    # Не даём пользоваться ботом до согласия с правилами
    user_router.message.middleware(RulesAcceptanceMiddleware())
    user_router.callback_query.middleware(RulesAcceptanceMiddleware())

    # Менеджер: /manager и callback'и mgr:*
    manager_router.message.middleware(BlockedUserMiddleware())
    manager_router.callback_query.middleware(BlockedUserMiddleware())
    manager_router.message.middleware(RulesAcceptanceMiddleware())
    manager_router.callback_query.middleware(RulesAcceptanceMiddleware())
    manager_router.message.middleware(ManagerOnlyMiddleware())
    manager_router.callback_query.middleware(ManagerOnlyMiddleware())
    dp.include_router(manager_router)

    # Команды set_welcome / set_help / set_min_* — и у админа, и у менеджера
    staff_settings_router.message.middleware(BlockedUserMiddleware())
    staff_settings_router.message.middleware(AdminOrManagerMiddleware())
    staff_settings_router.message.middleware(RulesAcceptanceMiddleware())
    dp.include_router(staff_settings_router)

    # Админ-роутер: только ADMIN_IDS
    admin_router.message.middleware(AdminOnlyMiddleware())
    admin_router.message.middleware(RulesAcceptanceMiddleware())
    admin_router.callback_query.middleware(AdminOnlyMiddleware())
    admin_router.callback_query.middleware(RulesAcceptanceMiddleware())
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