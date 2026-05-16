# -*- coding: utf-8 -*-
"""Сразу после скрина отзыва — фото админам без кнопок (кнопки приходят по таймеру в review_scheduler)."""
from aiogram import Bot

from config import ADMIN_IDS, REVIEW_CHECK_DAYS, REVIEW_REMINDER_AFTER_MINUTES


async def notify_admins_review_screenshot_received(
    bot: Bot,
    *,
    review_file_id: str,
    attempt_user_id: int,
    executor_username: str | None,
    task_platform: str,
    task_sphere: str,
    task_price: float,
    profile_login: str | None = None,
) -> None:
    uname = f"@{executor_username}" if executor_username else "(без username)"
    caption = (
        "✍️ Исполнитель написал отзыв и прислал скриншот публикации.\n"
        f"Исполнитель: {uname}\n"
        f"Telegram ID: {attempt_user_id}\n"
        f"Логин профиля: {(profile_login or '—')}\n"
        f"Задание: {task_platform} / {task_sphere}\n"
        f"Цена: {task_price:.2f} руб.\n\n"
        f"Проверьте отзыв на площадке в течение {REVIEW_CHECK_DAYS} дней.\n"
        f"Через ~{REVIEW_REMINDER_AFTER_MINUTES} мин. придёт напоминание с этим скрином "
        f"и кнопками «Принять» / «Отклонить»."
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_photo(admin_id, review_file_id, caption=caption)
        except Exception:
            pass
