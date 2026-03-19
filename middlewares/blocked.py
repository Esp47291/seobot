"""Блокировка пользователей по флагу в БД."""
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import ADMIN_IDS
from database import UserRepository


BLOCKED_TEXT = (
    "вы заблокированы по решению администрации, для разблокировки обратитесь к владельцу - @Exxzest"
)


class BlockedUserMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # DbSessionMiddleware обязан создать data['session']
        session = data.get("session")
        if not session:
            return await handler(event, data)

        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id is None:
            return await handler(event, data)

        # Админам блокировка не нужна
        if user_id in ADMIN_IDS:
            return await handler(event, data)

        user_repo = UserRepository(session)
        user = await user_repo.get_by_user_id(user_id)
        if user and user.is_blocked:
            if isinstance(event, Message):
                await event.answer(BLOCKED_TEXT)
            else:
                await event.answer(BLOCKED_TEXT, show_alert=True)
            return None

        return await handler(event, data)

