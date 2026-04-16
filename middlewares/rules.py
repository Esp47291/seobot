# -*- coding: utf-8 -*-
"""Middleware: gating access until user accepts bot rules."""

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, TelegramObject

from config import ADMIN_IDS
from database import UserRepository

from .blocked import BLOCKED_TEXT


RULES_ACCEPT_CALLBACK_DATA = "rules:accept"

PROXY_URL = (
    "https://t.me/proxy?server=151.247.208.232&port=443&secret="
    "dd2bf25ac71c3c6048e5f45933836a5c1f"
)

RULES_TEXT = (
    "🤝 Добро пожаловать в Job Inside бот!\n\n"
    "👑 Мы те, кто платит ВАМ за написание отзывов.\n\n"
    "❗️ Начать очень просто:\n"
    "♻️ Выбираете задание\n"
    "📃 Получаете инструкцию\n"
    "✍🏻 Пишете отзыв по инструкции\n"
    "💰 Получаете оплату за работу\n\n"
    "👥 Двухуровневая система рефералов (пассивный заработок)\n"
    "   1️⃣ уровень - 20% от заработка реферала\n"
    "   2️⃣ уровень - 5% от заработка реферала\n\n"
    "♻️ Расценки, периодичность выполнения и ответы на прочие вопросы вы можете найти ЗДЕСЬ "
    "https://t.me/Jobinsidenews\n\n"
    "⚙️ Наблюдаются проблемы с работой Telegram, а также загрузкой скриншотов! "
    "Подключите бесплатные мобильные прокси, чтобы избавиться от этих проблем 👇🏻\n\n"
    f"⚙️ Мобильные прокси ({PROXY_URL})\n\n"
)


def build_rules_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⚙️ Мобильные прокси", url=PROXY_URL)],
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

