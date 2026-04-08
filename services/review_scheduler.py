"""Планировщик: напоминание админу о проверке отзыва (без кнопок, чтобы не спамить)."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import ADMIN_IDS, REVIEW_CHECK_DAYS, REVIEW_SCHEDULER_INTERVAL_MINUTES
from database import AttemptRepository, TaskItemRepository, get_async_session


async def check_due_reviews(bot) -> None:
    async for session in get_async_session():
        attempt_repo = AttemptRepository(session)
        task_repo = TaskItemRepository(session)
        due_attempts = await attempt_repo.due_for_review_check()
        for attempt in due_attempts:
            task = await task_repo.get_by_id(attempt.task_item_id)
            if not task:
                await attempt_repo.mark_review_check_requested(attempt.id)
                continue
            for admin_id in ADMIN_IDS:
                try:
                    vc = (getattr(task, "venue_city", None) or "").strip() or "—"
                    await bot.send_message(
                        admin_id,
                        "⏰ <b>Напоминание: проверить отзыв</b>\n"
                        f"Attempt #{attempt.id}\n"
                        f"Исполнитель ID: <code>{attempt.user_id}</code>\n"
                        f"Задание: {task.platform} | город орг.: {vc} | сфера: {task.sphere} | {float(task.price):.2f} руб.\n\n"
                        f"Рекомендуем проверить в течение {REVIEW_CHECK_DAYS} дн.\n"
                        "Откройте: /admin → «📝 Подтверждение отзывов» (там ссылка, скрин и кнопки).",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
            await attempt_repo.mark_review_check_requested(attempt.id)


def start_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_due_reviews,
        "interval",
        minutes=max(1, REVIEW_SCHEDULER_INTERVAL_MINUTES),
        kwargs={"bot": bot},
        max_instances=1,
    )
    scheduler.start()
    return scheduler
