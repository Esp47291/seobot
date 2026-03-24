# -*- coding: utf-8 -*-
"""Доступ только для менеджеров (MANAGER_IDS)."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import MANAGER_IDS


class ManagerOnlyMiddleware(BaseMiddleware):
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
        if user_id is None or user_id not in MANAGER_IDS:
            if isinstance(event, CallbackQuery):
                await event.answer("Доступ только для менеджеров.", show_alert=True)
            return
        return await handler(event, data)
