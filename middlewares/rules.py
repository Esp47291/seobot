# -*- coding: utf-8 -*-
"""Middleware: gating access until user accepts bot rules."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from config import ADMIN_IDS
from database import UserRepository

from .blocked import BLOCKED_TEXT


RULES_ACCEPT_CALLBACK_DATA = "rules:accept"

RULES_TEXT = (
    "🤝 Добро пожаловать в Job Inside!\n\n"
    "Как это работает:\n"
    "1) Выбираете задание\n"
    "2) Получаете инструкцию\n"
    "3) Пишете отзыв и отправляете скрин\n"
    "4) Получаете оплату\n\n"
    "⚠️ Важно:\n"
    "• Выполняйте задания только со своего аккаунта\n"
    "• Следуйте инструкции без отклонений\n"
    "• Скрин отправляйте сразу после публикации\n"
)


def build_rules_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Принять правила", callback_data=RULES_ACCEPT_CALLBACK_DATA)],
        ]
    )


class RulesAcceptanceMiddleware(BaseMiddleware):
    """Blocks all handlers until the user accepts bot rules."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if session is None:
            return await handler(event, data)

        user_id = None
        from_user = None
        if isinstance(event, Message):
            from_user = event.from_user
        elif isinstance(event, CallbackQuery):
            from_user = event.from_user

        if from_user:
            user_id = from_user.id
        if user_id is None:
            return await handler(event, data)

        user_repo = UserRepository(session)
        user, _created = await user_repo.get_or_create(
            user_id=user_id,
            username=getattr(from_user, "username", None),
            first_name=getattr(from_user, "first_name", None),
        )

        # Admins/managers still must accept rules (as requested),
        # but blocked users should see the blocked message.
        if user.is_blocked and user_id not in ADMIN_IDS:
            if isinstance(event, Message):
                await event.answer(BLOCKED_TEXT)
            else:
                await event.answer(BLOCKED_TEXT, show_alert=True)
            return None

        if user.rules_accepted:
            return await handler(event, data)

        # Allow acceptance callback through.
        if isinstance(event, CallbackQuery):
            cb_data = event.data or ""
            if cb_data == RULES_ACCEPT_CALLBACK_DATA:
                return await handler(event, data)

        # Not accepted yet: show rules only once.
        if isinstance(event, Message):
            if not user.rules_prompted:
                await event.answer(RULES_TEXT, reply_markup=build_rules_keyboard())
                user.rules_prompted = True
                await session.flush()
            else:
                await event.answer("Сначала примите правила, чтобы пользоваться ботом.")
            return None

        # CallbackQuery
        cb: CallbackQuery = event
        if not (user.rules_prompted):
            await cb.message.answer(RULES_TEXT, reply_markup=build_rules_keyboard())
            user.rules_prompted = True
            await session.flush()
        else:
            await cb.answer("Сначала примите правила, чтобы пользоваться ботом.", show_alert=True)
        return None

