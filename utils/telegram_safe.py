# -*- coding: utf-8 -*-
"""Безопасные обёртки вокруг Telegram API (чтобы ошибка UI не откатывала транзакцию БД)."""
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message

logger = logging.getLogger(__name__)


async def safe_remove_reply_markup(message: Message | None) -> None:
    """Снимает inline-клавиатуру; игнорирует «message is not modified» и т.п."""
    if message is None:
        return
    try:
        await message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest as e:
        logger.debug("edit_reply_markup skipped: %s", e)


async def send_screenshot_or_document(bot: Bot, chat_id: int, file_id: str, **kwargs) -> None:
    """
    Скрин мог быть сохранён как photo file_id или как document file_id — для второго sendPhoto падает.
    """
    try:
        await bot.send_photo(chat_id, photo=file_id, **kwargs)
    except TelegramBadRequest:
        await bot.send_document(chat_id, document=file_id, **kwargs)
