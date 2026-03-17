"""Планировщик проверки отзывов спустя 3 дня."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import ADMIN_IDS, SCHEDULER_INTERVAL_MINUTES
from database import AttemptRepository, TaskItemRepository, get_async_session
from keyboards.admin import moderation_kb


async def check_due_reviews(bot) -> None:
    async for session in get_async_session():
        attempt_repo = AttemptRepository(session)
        task_repo = TaskItemRepository(session)
        due_attempts = await attempt_repo.due_for_review_check()
        for attempt in due_attempts:
            task = await task_repo.get_by_id(attempt.task_item_id)
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_photo(
                        admin_id,
                        attempt.review_screenshot_file_id,
                        caption=(
                            "⏰ Требуется проверка отзыва!\n"
                            f"Пользователь: {attempt.user_id}\n"
                            f"Задание: {task.platform} / {task.sphere}\n"
                            f"Ссылка на отзыв/инструкция: {task.instruction_url}\n"
                            f"Дата отправки скрина: {attempt.submitted_at:%d.%m.%Y %H:%M}"
                        ),
                        reply_markup=moderation_kb(attempt.id, "review"),
                    )
                except Exception:
                    pass
            await attempt_repo.mark_review_check_requested(attempt.id)


def start_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        check_due_reviews,
        "interval",
        minutes=SCHEDULER_INTERVAL_MINUTES,
        kwargs={"bot": bot},
        max_instances=1,
    )
    scheduler.start()
    return scheduler
