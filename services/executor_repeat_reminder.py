# -*- coding: utf-8 -*-
"""Напоминания исполнителям: отсчёт от момента отправки скрина отзыва на проверку (submitted_at + N часов)."""
from datetime import datetime, timedelta

from aiogram import Bot

from database import ExecutorReminderRepository, SettingsRepository, get_async_session
from database.models import BotSetting
from keyboards.user import main_menu


def reminder_hours_for_platform(platform: str, settings: BotSetting) -> int:
    p = (platform or "").strip()
    if p == "Яндекс карты":
        return int(getattr(settings, "reminder_hours_yandex", None) or 60)
    if p == "2ГИС":
        return int(getattr(settings, "reminder_hours_2gis", None) or 24)
    if p == "Google карты":
        return int(getattr(settings, "reminder_hours_google", None) or 24)
    return int(getattr(settings, "reminder_hours_other", None) or 24)


async def schedule_executor_repeat_reminder(
    session, user_id: int, platform: str, *, anchor: datetime | None = None
) -> None:
    """Ставит (перезаписывает) одно ожидающее напоминание для user+platform.

    anchor — момент начала отсчёта (обычно submitted_at при отправке скрина на проверку).
    Если не передан, используется текущее время (редкий fallback).
    """
    settings = await SettingsRepository(session).get()
    hours = reminder_hours_for_platform(platform, settings)
    hours = max(1, min(hours, 24 * 90))  # 1 ч … 90 дн.
    start = anchor if anchor is not None else datetime.utcnow()
    remind_at = start + timedelta(hours=hours)
    repo = ExecutorReminderRepository(session)
    await repo.reschedule(user_id, platform, remind_at)


async def process_due_executor_reminders(bot: Bot) -> None:
    async for session in get_async_session():
        repo = ExecutorReminderRepository(session)
        due = await repo.find_due()
        for row in due:
            text = (
                f"🔔 Напоминание: вы снова можете взять задание на платформе «{row.platform}».\n\n"
                "Нажмите «✍️ Приступить к заданию» в меню ниже."
            )
            try:
                await bot.send_message(row.user_id, text, reply_markup=main_menu())
            except Exception:
                pass
            await repo.mark_sent(row.id)
