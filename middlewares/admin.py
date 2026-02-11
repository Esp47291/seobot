# -*- coding: utf-8 -*-
"""Проверка доступа только для админов (по ADMIN_IDS)."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from config import ADMIN_IDS


class AdminOnlyMiddleware(BaseMiddleware):
    """Пропускает только пользователей из ADMIN_IDS. Использовать для админ-роутеров."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        if user_id is None or user_id not in ADMIN_IDS:
            if isinstance(event, CallbackQuery):
                await event.answer("Доступ запрещён.", show_alert=True)
            return
        return await handler(event, data)
