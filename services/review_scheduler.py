"""Планировщик: напоминание админу о проверке отзыва (без кнопок, чтобы не спамить)."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    ADMIN_IDS,
    EXECUTOR_REMINDER_INTERVAL_MINUTES,
    REVIEW_CHECK_DAYS,
    REVIEW_SCHEDULER_INTERVAL_MINUTES,
    TASK_EXECUTION_TIMEOUT_MINUTES,
)
from database import AttemptRepository, TaskItemRepository, UserRepository, get_async_session
from services.executor_repeat_reminder import process_due_executor_reminders


async def check_due_reviews(bot) -> None:
    async for session in get_async_session():
        attempt_repo = AttemptRepository(session)
        task_repo = TaskItemRepository(session)
        user_repo = UserRepository(session)
        due_attempts = await attempt_repo.due_for_review_check()
        for attempt in due_attempts:
            task = await task_repo.get_by_id(attempt.task_item_id)
            if not task:
                await attempt_repo.mark_review_check_requested(attempt.id)
                continue
            u = await user_repo.get_by_user_id(attempt.user_id)
            uname = f"@{u.username}" if u and u.username else "—"
            for admin_id in ADMIN_IDS:
                try:
                    vc = (getattr(task, "venue_city", None) or "").strip() or "—"
                    await bot.send_message(
                        admin_id,
                        "⏰ <b>Напоминание: проверить отзыв</b>\n"
                        f"Attempt #{attempt.id}\n"
                        f"Исполнитель: {uname}\n"
                        f"Исполнитель ID: <code>{attempt.user_id}</code>\n"
                        f"Логин профиля: <b>{(getattr(attempt, 'profile_login', None) or '—')}</b>\n"
                        f"Задание: {task.platform} | город орг.: {vc} | сфера: {task.sphere} | {float(task.price):.2f} руб.\n\n"
                        f"Рекомендуем проверить в течение {REVIEW_CHECK_DAYS} дн.\n"
                        "Откройте: /admin → «📝 Подтверждение отзывов» (там ссылка, скрин и кнопки).",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            await attempt_repo.mark_review_check_requested(attempt.id)


async def close_stale_executor_attempts(bot) -> None:
    """Если исполнитель слишком долго не прислал скрин отзыва — попытка закрывается."""
    async for session in get_async_session():
        attempt_repo = AttemptRepository(session)
        stale = await attempt_repo.due_for_execution_timeout(TASK_EXECUTION_TIMEOUT_MINUTES)
        for at in stale:
            canceled = await attempt_repo.timeout_cancel(
                at.id,
                "К сожалению, активное задание больше не доступно для вас, так как вы слишком долго выполняли его.",
            )
            if not canceled:
                continue
            try:
                await bot.send_message(
                    canceled.user_id,
                    "📝 К сожалению, активное задание больше не доступно для вас, так как вы слишком долго выполняли его.",
                )
            except Exception:
                pass


def start_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_due_reviews,
        "interval",
        minutes=max(1, REVIEW_SCHEDULER_INTERVAL_MINUTES),
        kwargs={"bot": bot},
        max_instances=1,
    )
    scheduler.add_job(
        process_due_executor_reminders,
        "interval",
        minutes=max(1, EXECUTOR_REMINDER_INTERVAL_MINUTES),
        kwargs={"bot": bot},
        max_instances=1,
    )
    scheduler.add_job(
        close_stale_executor_attempts,
        "interval",
        minutes=1,
        kwargs={"bot": bot},
        max_instances=1,
    )
    scheduler.start()
    return scheduler
