"""Планировщик: напоминание админу со скрином отзыва и кнопками Принять/Отклонить."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import ADMIN_IDS, REVIEW_CHECK_DAYS, REVIEW_SCHEDULER_INTERVAL_MINUTES
from database import AttemptRepository, TaskItemRepository, get_async_session
from keyboards.admin import moderation_kb


async def check_due_reviews(bot) -> None:
    async for session in get_async_session():
        attempt_repo = AttemptRepository(session)
        task_repo = TaskItemRepository(session)
        due_attempts = await attempt_repo.due_for_review_check()
        for attempt in due_attempts:
            task = await task_repo.get_by_id(attempt.task_item_id)
            if not task or not attempt.review_screenshot_file_id:
                await attempt_repo.mark_review_check_requested(attempt.id)
                continue
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_photo(
                        admin_id,
                        attempt.review_screenshot_file_id,
                        caption=(
                            "⏰ Напоминание: пора принять решение по отзыву.\n"
                            f"Исполнитель (ID): {attempt.user_id}\n"
                            f"Задание: {task.platform} | "
                            f"город орг.: {(getattr(task, 'venue_city', None) or '').strip() or '—'} | "
                            f"сфера: {task.sphere}\n"
                            f"Инструкция/ссылка: {task.instruction_url}\n"
                            f"Реквизиты исполнителя (из ЛК): {(attempt.payout_requisites or '—')[:500]}\n\n"
                            f"Проверьте отзыв на площадке (рекомендуем в течение {REVIEW_CHECK_DAYS} дн.).\n"
                            f"Скрин отправлен: {attempt.submitted_at:%d.%m.%Y %H:%M} UTC"
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
        minutes=max(1, REVIEW_SCHEDULER_INTERVAL_MINUTES),
        kwargs={"bot": bot},
        max_instances=1,
    )
    scheduler.start()
    return scheduler
