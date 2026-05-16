# -*- coding: utf-8 -*-
"""Репозитории для SeoJob / Отзовик."""
import json
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, delete, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from config import DEFAULT_MIN_WITHDRAW, MANAGER_IDS, REVIEW_REMINDER_AFTER_MINUTES, TASK_EXECUTION_TIMEOUT_MINUTES
from .models import (
    Attempt,
    BalanceOperation,
    BotSetting,
    ExecutorRepeatReminder,
    Referral,
    SecondAccountReview,
    TaskItem,
    User,
    WithdrawalRequest,
)


def _json_loads_map(raw: str | None) -> dict:
    if not raw or not str(raw).strip():
        return {}
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}

# Незавершённый цикл: нельзя начинать новое задание, пока есть такая попытка
_PIPELINE_ACTIVE_STATUSES = frozenset({"waiting_approval", "login_screenshot", "approved", "review_submitted"})


def _executor_sees_task_filter(user_profile_city: str | None):
    """Задание показывается исполнителю: city=* или совпадает с городом в профиле."""
    c = (user_profile_city or "").strip()
    if c:
        return or_(TaskItem.city == "*", TaskItem.city == c)
    return TaskItem.city == "*"


def _venue_city_match_empty():
    """Задание без указанного города организации (venue_city пустой)."""
    return func.length(func.trim(func.coalesce(TaskItem.venue_city, ""))) == 0


def _venue_city_match_value(venue_city: str):
    return func.trim(TaskItem.venue_city) == venue_city.strip()


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int, username: str | None, first_name: str | None) -> tuple[User, bool]:
        user = await self.get_by_user_id(user_id)
        if user:
            user.username = username
            user.first_name = first_name
            await self.session.flush()
            return user, False
        user = User(user_id=user_id, username=username, first_name=first_name)
        self.session.add(user)
        await self.session.flush()
        return user, True

    async def get_by_user_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.user_id == user_id))
        return result.scalar_one_or_none()

    async def get_by_username(self, username: str) -> User | None:
        result = await self.session.execute(select(User).where(User.username == username.lstrip("@")))
        return result.scalar_one_or_none()

    async def set_city(self, user_id: int, city: str) -> None:
        user = await self.get_by_user_id(user_id)
        if user:
            user.city = city
            await self.session.flush()

    async def set_account_gender(self, user_id: int, gender: str) -> None:
        user = await self.get_by_user_id(user_id)
        if user:
            user.account_gender = (gender or "any").strip()
            await self.session.flush()

    async def mark_welcome_bonus_credited(self, user_id: int) -> None:
        user = await self.get_by_user_id(user_id)
        if user:
            user.welcome_bonus_credited = True
            await self.session.flush()

    async def set_profile_payout_requisites(self, user_id: int, text: str | None) -> None:
        user = await self.get_by_user_id(user_id)
        if user:
            user.payout_requisites = text
            await self.session.flush()

    async def add_balance(self, user_id: int, amount: float) -> None:
        user = await self.get_by_user_id(user_id)
        if user:
            user.balance = Decimal(user.balance) + Decimal(str(amount))
            await self.session.flush()

    async def sub_balance(self, user_id: int, amount: float) -> bool:
        user = await self.get_by_user_id(user_id)
        if not user:
            return False
        if Decimal(user.balance) < Decimal(str(amount)):
            return False
        user.balance = Decimal(user.balance) - Decimal(str(amount))
        await self.session.flush()
        return True

    async def set_blocked(self, user_id: int, value: bool) -> None:
        user = await self.get_by_user_id(user_id)
        if user:
            user.is_blocked = value
            await self.session.flush()

    async def get_task_rotation_map(self, user_id: int) -> dict:
        user = await self.get_by_user_id(user_id)
        if not user:
            return {}
        return _json_loads_map(getattr(user, "task_rotation_json", None) or "{}")

    async def set_last_started_task_for_platform(self, user_id: int, platform: str, task_item_id: int) -> None:
        user = await self.get_by_user_id(user_id)
        if not user:
            return
        m = _json_loads_map(getattr(user, "task_rotation_json", None))
        m[platform] = task_item_id
        user.task_rotation_json = json.dumps(m, ensure_ascii=False)
        await self.session.flush()

    async def get_repeat_unlock_map(self, user_id: int) -> dict:
        user = await self.get_by_user_id(user_id)
        if not user:
            return {}
        return _json_loads_map(getattr(user, "repeat_unlock_json", None) or "{}")

    async def set_repeat_unlock_platform(self, user_id: int, platform: str, enabled: bool = True) -> None:
        user = await self.get_by_user_id(user_id)
        if not user:
            return
        m = _json_loads_map(getattr(user, "repeat_unlock_json", None))
        if enabled:
            m[platform] = True
        else:
            m.pop(platform, None)
        user.repeat_unlock_json = json.dumps(m, ensure_ascii=False)
        await self.session.flush()

    async def clear_repeat_unlock_platform(self, user_id: int, platform: str) -> None:
        await self.set_repeat_unlock_platform(user_id, platform, enabled=False)


class TaskItemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_venue_city_pick_list(self, user_profile_city: str | None) -> tuple[list[str], bool]:
        """
        Города организаций (venue_city) среди активных заданий, видимых исполнителю.
        Второй элемент — есть ли задания с пустым venue_city (отдельная кнопка в боте).
        """
        result = await self.session.execute(
            select(TaskItem.venue_city).where(TaskItem.is_active == True, _executor_sees_task_filter(user_profile_city))
        )
        nonempty: set[str] = set()
        has_empty = False
        for vc in result.scalars().all():
            s = (vc or "").strip()
            if not s:
                has_empty = True
            else:
                nonempty.add(s)
        ordered = sorted(nonempty, key=lambda x: x.casefold())
        return ordered, has_empty

    async def get_platforms_for_venue(self, venue_city: str | None, user_profile_city: str | None) -> list[str]:
        """Платформы с активными заданиями в выбранном городе организации (None = только без города)."""
        conds = [
            TaskItem.is_active == True,
            _executor_sees_task_filter(user_profile_city),
            _venue_city_match_empty() if venue_city is None else _venue_city_match_value(venue_city),
        ]
        r = await self.session.execute(
            select(TaskItem.platform).where(*conds).group_by(TaskItem.platform).order_by(TaskItem.platform)
        )
        return list(r.scalars().all())

    async def get_platforms_with_min_price(self, user_profile_city: str | None) -> list[tuple[str, float]]:
        result = await self.session.execute(
            select(TaskItem.platform, func.min(TaskItem.price))
            .where(TaskItem.is_active == True, _executor_sees_task_filter(user_profile_city))
            .group_by(TaskItem.platform)
            .order_by(TaskItem.platform)
        )
        return [(p, float(v or 0)) for p, v in result.all()]

    async def get_active_for_platform(self, platform: str, user_profile_city: str | None) -> list[TaskItem]:
        result = await self.session.execute(
            select(TaskItem)
            .where(
                TaskItem.platform == platform,
                TaskItem.is_active == True,
                _executor_sees_task_filter(user_profile_city),
            )
            .order_by(TaskItem.id)
        )
        tasks = list(result.scalars().all())
        return await self._filter_by_daily_issue_count(tasks)

    async def get_active_for_venue_platform(
        self, venue_city: str | None, platform: str, user_profile_city: str | None
    ) -> list[TaskItem]:
        conds = [
            TaskItem.platform == platform,
            TaskItem.is_active == True,
            _executor_sees_task_filter(user_profile_city),
            _venue_city_match_empty() if venue_city is None else _venue_city_match_value(venue_city),
        ]
        r = await self.session.execute(select(TaskItem).where(*conds).order_by(TaskItem.id))
        tasks = list(r.scalars().all())
        return await self._filter_by_daily_issue_count(tasks)

    async def get_platforms_by_city(self, city: str) -> list[str]:
        result = await self.session.execute(
            select(TaskItem.platform)
            .where(
                TaskItem.is_active == True,
                or_(TaskItem.city == city, TaskItem.city == "*"),
            )
            .group_by(TaskItem.platform)
            .order_by(TaskItem.platform)
        )
        return list(result.scalars().all())

    async def get_active_for_city_platform(self, city: str, platform: str) -> list[TaskItem]:
        result = await self.session.execute(
            select(TaskItem)
            .where(
                TaskItem.platform == platform,
                TaskItem.is_active == True,
                or_(TaskItem.city == city, TaskItem.city == "*"),
            )
            .order_by(TaskItem.id)
        )
        tasks = list(result.scalars().all())
        return await self._filter_by_daily_issue_count(tasks)

    async def get_by_id(self, task_item_id: int) -> TaskItem | None:
        result = await self.session.execute(select(TaskItem).where(TaskItem.id == task_item_id))
        return result.scalar_one_or_none()

    async def get_all(self) -> list[TaskItem]:
        result = await self.session.execute(select(TaskItem).order_by(TaskItem.id.desc()))
        return list(result.scalars().all())

    async def create(
        self,
        platform: str,
        city: str,
        sphere: str,
        venue_city: str,
        price: float,
        instruction_url: str,
        daily_issue_count: int | None = None,
        prebuilt_texts_json: str = "[]",
        created_by_user_id: int | None = None,
        allowed_gender: str = "any",
    ) -> TaskItem:
        # Минимальная цена в зависимости от платформы
        settings = await SettingsRepository(self.session).get()
        min_price = self._min_price_for_platform(platform, settings)
        if min_price is not None and price < min_price:
            raise ValueError(f"Цена для платформы '{platform}' не может быть ниже {min_price} руб.")

        task = TaskItem(
            platform=platform,
            city=city,
            sphere=sphere,
            venue_city=(venue_city or "").strip(),
            price=price,
            instruction_url=instruction_url,
            daily_issue_count=daily_issue_count,
            prebuilt_texts_json=prebuilt_texts_json,
            created_by_user_id=created_by_user_id,
            allowed_gender=(allowed_gender or "any").strip(),
        )
        self.session.add(task)
        await self.session.flush()
        return task

    async def _filter_by_daily_issue_count(self, tasks: list[TaskItem]) -> list[TaskItem]:
        """Фильтрует задания по дневному лимиту выдачи."""
        if not tasks:
            return []

        limited = [t for t in tasks if getattr(t, "daily_issue_count", None) is not None and int(t.daily_issue_count) > 0]
        if not limited:
            return tasks

        start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        ids = [t.id for t in limited]

        result = await self.session.execute(
            select(Attempt.task_item_id, func.count())
            .where(
                Attempt.task_item_id.in_(ids),
                Attempt.created_at >= start,
                Attempt.created_at < end,
                Attempt.status.notin_(["declined", "canceled"]),
            )
            .group_by(Attempt.task_item_id)
        )
        used_map: dict[int, int] = {int(task_id): int(cnt) for task_id, cnt in result.all()}

        filtered: list[TaskItem] = []
        for t in tasks:
            lim = getattr(t, "daily_issue_count", None)
            if lim is None:
                filtered.append(t)
                continue
            used = used_map.get(int(t.id), 0)
            if used < int(lim):
                filtered.append(t)
        return filtered

    async def update_field(self, task_item_id: int, field_name: str, value: str) -> bool:
        task = await self.get_by_id(task_item_id)
        if not task or not hasattr(task, field_name):
            return False
        if field_name == "price":
            settings = await SettingsRepository(self.session).get()
            min_price = self._min_price_for_platform(task.platform, settings)
            new_price = Decimal(value)
            if min_price is not None and new_price < Decimal(str(min_price)):
                return False
            setattr(task, field_name, new_price)
        else:
            setattr(task, field_name, value)
        await self.session.flush()
        return True

    def _min_price_for_platform(self, platform: str, settings: BotSetting) -> int | None:
        if platform == "Яндекс карты":
            return int(settings.min_review_price_yandex)
        if platform == "Google карты":
            return int(settings.min_review_price_google)
        if platform == "2ГИС":
            return int(settings.min_review_price_2gis)
        return None

    async def toggle_active(self, task_item_id: int) -> bool:
        task = await self.get_by_id(task_item_id)
        if not task:
            return False
        task.is_active = not task.is_active
        await self.session.flush()
        return True

    async def delete(self, task_item_id: int) -> bool:
        task = await self.get_by_id(task_item_id)
        if not task:
            return False
        await self.session.delete(task)
        await self.session.flush()
        return True

    async def get_by_creator(self, creator_user_id: int) -> list[TaskItem]:
        result = await self.session.execute(
            select(TaskItem).where(TaskItem.created_by_user_id == creator_user_id).order_by(TaskItem.id.desc())
        )
        return list(result.scalars().all())

    async def deactivate_all_for_manager(self, manager_user_id: int) -> int:
        """Выключает все активные задания менеджера. Возвращает число изменённых строк."""
        result = await self.session.execute(
            select(TaskItem).where(
                TaskItem.created_by_user_id == manager_user_id,
                TaskItem.is_active == True,
            )
        )
        rows = list(result.scalars().all())
        for t in rows:
            t.is_active = False
        await self.session.flush()
        return len(rows)


class AttemptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, task_item_id: int) -> Attempt:
        attempt = Attempt(user_id=user_id, task_item_id=task_item_id, status="waiting_approval")
        self.session.add(attempt)
        await self.session.flush()
        return attempt

    async def set_profile_login(self, attempt_id: int, profile_login: str) -> Attempt | None:
        attempt = await self.get_by_id(attempt_id)
        if not attempt:
            return None
        attempt.profile_login = (profile_login or "").strip()[:255]
        await self.session.flush()
        return attempt

    async def get_by_id(self, attempt_id: int) -> Attempt | None:
        result = await self.session.execute(select(Attempt).where(Attempt.id == attempt_id))
        return result.scalar_one_or_none()

    async def get_last_by_user_status(self, user_id: int, status: str) -> Attempt | None:
        result = await self.session.execute(
            select(Attempt)
            .where(Attempt.user_id == user_id, Attempt.status == status)
            .order_by(Attempt.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_active_pipeline_attempt(self, user_id: int) -> Attempt | None:
        """Попытка в процессе (профиль/отзыв на проверке и т.д.) — блокирует старт другого задания."""
        result = await self.session.execute(
            select(Attempt)
            .where(Attempt.user_id == user_id, Attempt.status.in_(_PIPELINE_ACTIVE_STATUSES))
            .order_by(Attempt.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def completed_task_item_ids(self, user_id: int) -> set[int]:
        """ID заданий, которые пользователь уже успешно завершил (статус completed)."""
        result = await self.session.execute(
            select(Attempt.task_item_id).where(Attempt.user_id == user_id, Attempt.status == "completed")
        )
        return {int(row[0]) for row in result.all()}

    async def set_account_screenshot(self, attempt_id: int, file_id: str) -> None:
        attempt = await self.get_by_id(attempt_id)
        if attempt:
            attempt.account_screenshot_file_id = file_id
            attempt.status = "login_screenshot"
            await self.session.flush()

    async def approve(self, attempt_id: int) -> Attempt | None:
        attempt = await self.get_by_id(attempt_id)
        if not attempt:
            return None
        # Допуск нажимают по заявке в очереди; иначе повторный клик не должен откатывать БД из‑за Telegram.
        if attempt.status not in ("waiting_approval", "login_screenshot"):
            return None
        attempt.status = "approved"
        await self.session.flush()
        return attempt

    async def decline(self, attempt_id: int, reason: str) -> Attempt | None:
        attempt = await self.get_by_id(attempt_id)
        if attempt:
            attempt.status = "declined"
            attempt.decline_reason = reason
            await self.session.flush()
        return attempt

    async def cancel(self, attempt_id: int) -> None:
        attempt = await self.get_by_id(attempt_id)
        if attempt:
            attempt.status = "canceled"
            await self.session.flush()

    async def submit_review(self, attempt_id: int, file_id: str, payout_requisites: str) -> Attempt | None:
        """
        Скрин опубликованного отзыва. Статус должен быть approved.
        payout_requisites — копия из профиля исполнителя на момент отправки.
        check_after — когда прислать админу напоминание с кнопками (см. REVIEW_REMINDER_AFTER_MINUTES).
        """
        attempt = await self.get_by_id(attempt_id)
        if not attempt or attempt.status != "approved":
            return None
        if not (payout_requisites or "").strip():
            return None
        attempt.review_screenshot_file_id = file_id
        attempt.payout_requisites = payout_requisites.strip()
        attempt.status = "review_submitted"
        attempt.submitted_at = datetime.utcnow()
        attempt.check_after = attempt.submitted_at + timedelta(minutes=REVIEW_REMINDER_AFTER_MINUTES)
        attempt.review_check_requested = False
        await self.session.flush()
        return attempt

    async def complete(self, attempt_id: int) -> Attempt | None:
        attempt = await self.get_by_id(attempt_id)
        if not attempt:
            return None
        # Чтобы избежать двойных начислений при повторном нажатии
        if attempt.status != "review_submitted":
            return None
        attempt.status = "completed"
        await self.session.flush()
        return attempt

    async def mark_balance_credited(self, attempt_id: int) -> Attempt | None:
        attempt = await self.get_by_id(attempt_id)
        if not attempt or attempt.balance_credited:
            return None
        attempt.balance_credited = True
        await self.session.flush()
        return attempt

    async def reject(self, attempt_id: int, reason: str) -> Attempt | None:
        attempt = await self.get_by_id(attempt_id)
        if attempt:
            attempt.status = "rejected"
            attempt.reject_reason = reason
            await self.session.flush()
        return attempt

    async def due_for_review_check(self) -> list[Attempt]:
        result = await self.session.execute(
            select(Attempt).where(
                Attempt.status == "review_submitted",
                Attempt.check_after.is_not(None),
                Attempt.check_after < datetime.utcnow(),
                Attempt.review_check_requested == False,
            )
        )
        return list(result.scalars().all())

    async def due_for_execution_timeout(self, timeout_minutes: int | None = None) -> list[Attempt]:
        minutes = int(timeout_minutes or TASK_EXECUTION_TIMEOUT_MINUTES)
        minutes = max(1, minutes)
        border = datetime.utcnow() - timedelta(minutes=minutes)
        result = await self.session.execute(
            select(Attempt).where(
                Attempt.status == "approved",
                Attempt.review_screenshot_file_id.is_(None),
                Attempt.created_at <= border,
                Attempt.timeout_notified == False,
            )
        )
        return list(result.scalars().all())

    async def timeout_cancel(self, attempt_id: int, reason: str) -> Attempt | None:
        attempt = await self.get_by_id(attempt_id)
        if not attempt or attempt.status != "approved":
            return None
        attempt.status = "canceled"
        attempt.decline_reason = reason
        attempt.timeout_notified = True
        await self.session.flush()
        return attempt

    async def mark_review_check_requested(self, attempt_id: int) -> None:
        attempt = await self.get_by_id(attempt_id)
        if attempt:
            attempt.review_check_requested = True
            await self.session.flush()

    async def list_user_review_history(self, user_id: int, *, limit: int = 30) -> list[Attempt]:
        """Попытки, по которым исполнитель отправлял скрин отзыва на проверку."""
        result = await self.session.execute(
            select(Attempt)
            .where(
                Attempt.user_id == user_id,
                Attempt.review_screenshot_file_id.isnot(None),
                Attempt.status.in_(("review_submitted", "completed", "rejected")),
            )
            .order_by(Attempt.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def completed_count_by_user(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Attempt).where(Attempt.user_id == user_id, Attempt.status == "completed")
        )
        return int(result.scalar() or 0)


class SecondAccountReviewRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, review_id: int) -> SecondAccountReview | None:
        return await self.session.get(SecondAccountReview, review_id)

    async def get_pending_for_user(self, user_id: int) -> SecondAccountReview | None:
        result = await self.session.execute(
            select(SecondAccountReview)
            .where(SecondAccountReview.user_id == user_id, SecondAccountReview.status == "pending")
            .order_by(SecondAccountReview.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def create(self, user_id: int, platform: str, screenshot_file_id: str) -> SecondAccountReview:
        row = SecondAccountReview(
            user_id=user_id,
            platform=platform,
            screenshot_file_id=screenshot_file_id,
            status="pending",
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def approve(self, review_id: int) -> SecondAccountReview | None:
        row = await self.get_by_id(review_id)
        if not row or row.status != "pending":
            return None
        row.status = "approved"
        await self.session.flush()
        return row

    async def reject(self, review_id: int, reason: str | None = None) -> SecondAccountReview | None:
        row = await self.get_by_id(review_id)
        if not row or row.status != "pending":
            return None
        row.status = "rejected"
        row.decline_reason = reason
        await self.session.flush()
        return row

    async def list_pending(self, limit: int = 100) -> list[SecondAccountReview]:
        result = await self.session.execute(
            select(SecondAccountReview)
            .where(SecondAccountReview.status == "pending")
            .order_by(SecondAccountReview.id.asc())
            .limit(limit)
        )
        return list(result.scalars().all())


class BalanceRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add_operation(self, user_id: int, amount: float, operation_type: str, comment: str | None = None) -> None:
        op = BalanceOperation(
            user_id=user_id,
            amount=Decimal(str(amount)),
            operation_type=operation_type,
            comment=comment,
        )
        self.session.add(op)
        await self.session.flush()

    async def get_last_operations(self, user_id: int, limit: int = 10) -> list[BalanceOperation]:
        result = await self.session.execute(
            select(BalanceOperation)
            .where(BalanceOperation.user_id == user_id)
            .order_by(BalanceOperation.id.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class WithdrawalRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, amount: float, requisites: str) -> WithdrawalRequest:
        item = WithdrawalRequest(user_id=user_id, amount=Decimal(str(amount)), requisites=requisites, status="pending")
        self.session.add(item)
        await self.session.flush()
        return item

    async def get_by_id(self, withdrawal_id: int) -> WithdrawalRequest | None:
        result = await self.session.execute(select(WithdrawalRequest).where(WithdrawalRequest.id == withdrawal_id))
        return result.scalar_one_or_none()

    async def get_pending(self) -> list[WithdrawalRequest]:
        result = await self.session.execute(
            select(WithdrawalRequest).where(WithdrawalRequest.status == "pending").order_by(WithdrawalRequest.id.desc())
        )
        return list(result.scalars().all())

    async def mark_paid(self, withdrawal_id: int) -> WithdrawalRequest | None:
        item = await self.get_by_id(withdrawal_id)
        if item:
            item.status = "paid"
            item.processed_at = datetime.utcnow()
            await self.session.flush()
        return item

    async def mark_rejected(self, withdrawal_id: int) -> WithdrawalRequest | None:
        item = await self.get_by_id(withdrawal_id)
        if item:
            item.status = "rejected"
            item.processed_at = datetime.utcnow()
            await self.session.flush()
        return item


class SettingsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self) -> BotSetting:
        item = await self.session.get(BotSetting, 1)
        if item:
            # Backward-compatible default update:
            # existing SQLite DB may already have old default welcome_text stored.
            # We update only when it matches the previous built-in default to avoid
            # overriding custom admin/manager settings.
            old_default_welcome = "Добро пожаловать в SeoJob!\n\nВыберите действие в меню ниже."
            new_default_welcome = (
                "Добро пожаловать в Job Inside!\n\n"
                "Выберите действие в меню ниже — и начнем зарабатывать.\n\n"
                "✍️ Приступить к заданию\n"
                "💰 Личный кабинет / Баланс\n"
                "💸 Вывести средства\n"
                "👥 Реферальная программа\n"
                "🆘 Помощь"
            )
            if item.welcome_text.strip() == old_default_welcome.strip():
                item.welcome_text = new_default_welcome
                await self.session.flush()
            return item
        item = BotSetting(
            id=1,
            min_withdraw_amount=DEFAULT_MIN_WITHDRAW,
            min_review_price_yandex=130,
            min_review_price_google=35,
            min_review_price_2gis=12,
            reminder_hours_yandex=60,
            reminder_hours_2gis=24,
            reminder_hours_google=24,
            reminder_hours_other=24,
        )
        self.session.add(item)
        await self.session.flush()
        return item

    async def set_field(self, field_name: str, value) -> None:
        item = await self.get()
        setattr(item, field_name, value)
        await self.session.flush()


class ExecutorReminderRepository:
    """Напоминания исполнителю о возможности снова взять задание на платформе."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def reschedule(self, user_id: int, platform: str, remind_at: datetime) -> None:
        p = (platform or "").strip()
        await self.session.execute(
            delete(ExecutorRepeatReminder).where(
                ExecutorRepeatReminder.user_id == user_id,
                ExecutorRepeatReminder.platform == p,
                ExecutorRepeatReminder.sent.is_(False),
            )
        )
        self.session.add(
            ExecutorRepeatReminder(user_id=user_id, platform=p, remind_at=remind_at, sent=False)
        )
        await self.session.flush()

    async def find_due(self, limit: int = 200) -> list[ExecutorRepeatReminder]:
        now = datetime.utcnow()
        result = await self.session.execute(
            select(ExecutorRepeatReminder)
            .where(ExecutorRepeatReminder.sent.is_(False), ExecutorRepeatReminder.remind_at <= now)
            .order_by(ExecutorRepeatReminder.remind_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def mark_sent(self, reminder_id: int) -> None:
        row = await self.session.get(ExecutorRepeatReminder, reminder_id)
        if row:
            row.sent = True
            await self.session.flush()


class StatsRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def summary(self) -> dict:
        users_total = int((await self.session.execute(select(func.count()).select_from(User))).scalar() or 0)
        users_new_week = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(User).where(User.registered_at > datetime.utcnow() - timedelta(days=7))
                )
            ).scalar()
            or 0
        )
        tasks_completed = int(
            (await self.session.execute(select(func.count()).select_from(Attempt).where(Attempt.status == "completed"))).scalar() or 0
        )
        total_paid = (
            await self.session.execute(
                select(func.coalesce(func.sum(WithdrawalRequest.amount), 0)).where(WithdrawalRequest.status == "paid")
            )
        ).scalar()
        total_balances = (await self.session.execute(select(func.coalesce(func.sum(User.balance), 0)))).scalar()
        return {
            "users_total": users_total,
            "users_new_week": users_new_week,
            "tasks_completed": tasks_completed,
            "total_paid": float(total_paid or 0),
            "total_balances": float(total_balances or 0),
        }

    async def manager_completed_tasks(self, manager_user_id: int) -> int:
        """Сколько попыток по заданиям этого менеджера дошли до статуса completed."""
        result = await self.session.execute(
            select(func.count())
            .select_from(Attempt)
            .join(TaskItem, Attempt.task_item_id == TaskItem.id)
            .where(
                TaskItem.created_by_user_id == manager_user_id,
                Attempt.status == "completed",
            )
        )
        return int(result.scalar() or 0)

    async def admin_dashboard_extras(self) -> dict:
        """Дополнительные метрики только для админ-панели."""
        row = (
            await self.session.execute(
                select(func.count(WithdrawalRequest.id), func.coalesce(func.sum(WithdrawalRequest.amount), 0)).where(
                    WithdrawalRequest.status == "pending"
                )
            )
        ).one()
        reviews_pending = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(Attempt).where(Attempt.status == "review_submitted")
                )
            ).scalar()
            or 0
        )
        profiles_pending = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(Attempt).where(Attempt.status.in_(["waiting_approval", "login_screenshot"]))
                )
            ).scalar()
            or 0
        )
        manager_tasks = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(TaskItem).where(TaskItem.created_by_user_id.isnot(None))
                )
            ).scalar()
            or 0
        )
        admin_tasks = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(TaskItem).where(TaskItem.created_by_user_id.is_(None))
                )
            ).scalar()
            or 0
        )
        active_tasks = int(
            (await self.session.execute(select(func.count()).select_from(TaskItem).where(TaskItem.is_active == True))).scalar()
            or 0
        )
        ref_ops = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(BalanceOperation).where(
                        BalanceOperation.operation_type.in_(["referral_commission_l1", "referral_commission_l2"])
                    )
                )
            ).scalar()
            or 0
        )
        return {
            "pending_wd_count": int(row[0] or 0),
            "pending_wd_sum": float(row[1] or 0),
            "reviews_awaiting_admin": reviews_pending,
            "profiles_awaiting_admin": profiles_pending,
            "manager_tasks_total": manager_tasks,
            "admin_tasks_total": admin_tasks,
            "tasks_active_any_owner": active_tasks,
            "referral_payout_ops_total": ref_ops,
        }

    async def manager_ids_for_admin_report(self) -> list[int]:
        """ID менеджеров: из .env и из фактически созданных заданий."""
        result = await self.session.execute(
            select(TaskItem.created_by_user_id).where(TaskItem.created_by_user_id.isnot(None)).distinct()
        )
        from_db = {row[0] for row in result.all() if row[0] is not None}
        return sorted(from_db | set(MANAGER_IDS))

    async def per_manager_admin_snapshot(self, manager_user_id: int) -> dict:
        """Детальная сводка по одному менеджеру для админки."""
        u_row = await self.session.execute(select(User).where(User.user_id == manager_user_id))
        user = u_row.scalar_one_or_none()
        username = user.username if user else None

        t_result = await self.session.execute(
            select(TaskItem)
            .where(TaskItem.created_by_user_id == manager_user_id)
            .order_by(TaskItem.id.desc())
        )
        tasks: list[TaskItem] = list(t_result.scalars().all())
        tasks_total = len(tasks)
        tasks_active = sum(1 for t in tasks if t.is_active)

        executions_completed = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(Attempt)
                    .join(TaskItem, Attempt.task_item_id == TaskItem.id)
                    .where(TaskItem.created_by_user_id == manager_user_id, Attempt.status == "completed")
                )
            ).scalar()
            or 0
        )

        paid_count = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(Attempt)
                    .join(TaskItem, Attempt.task_item_id == TaskItem.id)
                    .where(
                        TaskItem.created_by_user_id == manager_user_id,
                        Attempt.status == "completed",
                        Attempt.balance_credited == True,
                    )
                )
            ).scalar()
            or 0
        )
        pending_pay_count = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(Attempt)
                    .join(TaskItem, Attempt.task_item_id == TaskItem.id)
                    .where(
                        TaskItem.created_by_user_id == manager_user_id,
                        Attempt.status == "completed",
                        Attempt.balance_credited == False,
                    )
                )
            ).scalar()
            or 0
        )

        sum_paid = float(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(TaskItem.price), 0))
                    .select_from(Attempt)
                    .join(TaskItem, Attempt.task_item_id == TaskItem.id)
                    .where(
                        TaskItem.created_by_user_id == manager_user_id,
                        Attempt.status == "completed",
                        Attempt.balance_credited == True,
                    )
                )
            ).scalar()
            or 0
        )
        sum_pending = float(
            (
                await self.session.execute(
                    select(func.coalesce(func.sum(TaskItem.price), 0))
                    .select_from(Attempt)
                    .join(TaskItem, Attempt.task_item_id == TaskItem.id)
                    .where(
                        TaskItem.created_by_user_id == manager_user_id,
                        Attempt.status == "completed",
                        Attempt.balance_credited == False,
                    )
                )
            ).scalar()
            or 0
        )

        # В работе: не завершённые попытки по заданиям менеджера
        in_progress = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(Attempt)
                    .join(TaskItem, Attempt.task_item_id == TaskItem.id)
                    .where(
                        TaskItem.created_by_user_id == manager_user_id,
                        Attempt.status.notin_(["completed", "declined", "rejected", "canceled"]),
                    )
                )
            ).scalar()
            or 0
        )

        task_lines = []
        for t in tasks[:25]:
            vc = (getattr(t, "venue_city", None) or "").strip() or "—"
            sp = (t.sphere or "").strip() or "—"
            sp_short = sp[:20] + "…" if len(sp) > 20 else sp
            task_lines.append(
                f"  • #{t.id} {t.platform} | {vc} | {sp_short} | {float(t.price):.2f} руб. | "
                f"{'ON' if t.is_active else 'OFF'}"
            )
        if tasks_total > 25:
            task_lines.append(f"  … и ещё {tasks_total - 25} заданий")

        return {
            "user_id": manager_user_id,
            "username": username,
            "tasks_total": tasks_total,
            "tasks_active": tasks_active,
            "task_lines": task_lines,
            "executions_completed": executions_completed,
            "paid_by_manager_count": paid_count,
            "awaiting_manager_payment_count": pending_pay_count,
            "sum_paid_out_rub": sum_paid,
            "sum_awaiting_manager_rub": sum_pending,
            "attempts_in_progress": in_progress,
        }

    async def moderation_hub_counts(self) -> dict[str, int]:
        admission = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(Attempt).where(Attempt.status == "waiting_approval")
                )
            ).scalar()
            or 0
        )
        reviews = int(
            (
                await self.session.execute(
                    select(func.count()).select_from(Attempt).where(Attempt.status == "review_submitted")
                )
            ).scalar()
            or 0
        )
        secacc = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(SecondAccountReview)
                    .where(SecondAccountReview.status == "pending")
                )
            ).scalar()
            or 0
        )
        withdrawals = int(
            (
                await self.session.execute(
                    select(func.count())
                    .select_from(WithdrawalRequest)
                    .where(WithdrawalRequest.status == "pending")
                )
            ).scalar()
            or 0
        )
        return {
            "admission": admission,
            "reviews": reviews,
            "second_account": secacc,
            "withdrawals": withdrawals,
        }

    async def export_completed_attempts_rows(self, dt_from: datetime, dt_to: datetime) -> list[dict]:
        OwnerUser = aliased(User, name="task_owner_user")
        result = await self.session.execute(
            select(Attempt, TaskItem, User, OwnerUser)
            .join(TaskItem, Attempt.task_item_id == TaskItem.id)
            .join(User, Attempt.user_id == User.user_id)
            .outerjoin(OwnerUser, TaskItem.created_by_user_id == OwnerUser.user_id)
            .where(
                Attempt.status == "completed",
                Attempt.updated_at >= dt_from,
                Attempt.updated_at <= dt_to,
            )
            .order_by(Attempt.id.asc())
        )
        out: list[dict] = []
        for attempt, task, executor, owner in result.all():
            if task.created_by_user_id is None:
                owner_type = "admin"
                owner_tid = ""
                owner_un = ""
            else:
                owner_type = "manager"
                owner_tid = str(task.created_by_user_id)
                owner_un = (owner.username or "") if owner is not None else ""
            req = (attempt.payout_requisites or "").replace("\n", " ").replace("\r", " ").strip()
            out.append(
                {
                    "attempt_id": attempt.id,
                    "task_id": task.id,
                    "instruction_url": (task.instruction_url or "").strip(),
                    "owner_type": owner_type,
                    "owner_telegram_id": owner_tid,
                    "owner_username": owner_un,
                    "platform": task.platform or "",
                    "venue_city": (getattr(task, "venue_city", None) or "").strip(),
                    "executor_telegram_id": str(attempt.user_id),
                    "executor_username": executor.username or "",
                    "task_price_rub": float(task.price or 0),
                    "balance_credited": "yes" if attempt.balance_credited else "no",
                    "payout_requisites": req,
                    "completed_at_utc": attempt.updated_at.isoformat() if attempt.updated_at else "",
                }
            )
        return out

    async def export_withdrawal_rows(self, dt_from: datetime, dt_to: datetime) -> list[dict]:
        result = await self.session.execute(
            select(WithdrawalRequest, User)
            .outerjoin(User, WithdrawalRequest.user_id == User.user_id)
            .where(WithdrawalRequest.created_at >= dt_from, WithdrawalRequest.created_at <= dt_to)
            .order_by(WithdrawalRequest.id.asc())
        )
        out: list[dict] = []
        for wd, u in result.all():
            req = (wd.requisites or "").replace("\n", " ").replace("\r", " ").strip()
            out.append(
                {
                    "withdrawal_id": wd.id,
                    "user_telegram_id": str(wd.user_id),
                    "username": (u.username or "") if u is not None else "",
                    "amount_rub": float(wd.amount or 0),
                    "status": wd.status or "",
                    "requisites": req,
                    "created_at_utc": wd.created_at.isoformat() if wd.created_at else "",
                    "processed_at_utc": wd.processed_at.isoformat() if wd.processed_at else "",
                }
            )
        return out

    async def managers_pending_payment_summary(self) -> list[tuple[int, int, float]]:
        """(manager_user_id, completed_awaiting_pay_count, sum_prices_rub)."""
        result = await self.session.execute(
            select(
                TaskItem.created_by_user_id,
                func.count(Attempt.id),
                func.coalesce(func.sum(TaskItem.price), 0),
            )
            .select_from(Attempt)
            .join(TaskItem, Attempt.task_item_id == TaskItem.id)
            .where(
                Attempt.status == "completed",
                Attempt.balance_credited.is_(False),
                TaskItem.created_by_user_id.isnot(None),
            )
            .group_by(TaskItem.created_by_user_id)
        )
        rows: list[tuple[int, int, float]] = []
        for uid, cnt, s in result.all():
            if uid is None:
                continue
            rows.append((int(uid), int(cnt or 0), float(s or 0)))
        return rows

    async def tasks_analytics_rows(
        self,
        *,
        owner_filter: str | None = None,
        manager_user_id: int | None = None,
        limit: int = 35,
    ) -> list[dict]:
        """
        owner_filter: None — все; \"admin\" — задания админа; \"manager\" — задания одного менеджера (нужен manager_user_id).
        """
        agg_sq = (
            select(
                Attempt.task_item_id.label("tid"),
                func.count(Attempt.id).label("attempts_total"),
                func.sum(case((Attempt.status == "completed", 1), else_=0)).label("completed_n"),
                func.sum(
                    case(
                        (
                            and_(
                                Attempt.status == "completed",
                                Attempt.balance_credited.is_(False),
                                TaskItem.created_by_user_id.isnot(None),
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ).label("awaiting_pay_n"),
                func.sum(
                    case(
                        (
                            and_(Attempt.status == "completed", Attempt.balance_credited.is_(True)),
                            1,
                        ),
                        else_=0,
                    )
                ).label("paid_out_n"),
            )
            .select_from(Attempt)
            .join(TaskItem, Attempt.task_item_id == TaskItem.id)
            .group_by(Attempt.task_item_id)
        ).subquery()

        q = (
            select(
                TaskItem,
                func.coalesce(agg_sq.c.attempts_total, 0).label("atn"),
                func.coalesce(agg_sq.c.completed_n, 0).label("done_n"),
                func.coalesce(agg_sq.c.awaiting_pay_n, 0).label("wait_n"),
                func.coalesce(agg_sq.c.paid_out_n, 0).label("paid_n"),
            )
            .select_from(TaskItem)
            .outerjoin(agg_sq, TaskItem.id == agg_sq.c.tid)
        )
        if owner_filter == "admin":
            q = q.where(TaskItem.created_by_user_id.is_(None))
        elif owner_filter == "manager" and manager_user_id is not None:
            q = q.where(TaskItem.created_by_user_id == manager_user_id)

        q = q.order_by(TaskItem.id.desc()).limit(limit)
        result = await self.session.execute(q)
        out: list[dict] = []
        for task, atn, done_n, wait_n, paid_n in result.all():
            owner = "админ" if task.created_by_user_id is None else f"менеджер {task.created_by_user_id}"
            vc = (getattr(task, "venue_city", None) or "").strip() or "—"
            sp = (task.sphere or "").strip() or "—"
            sp_short = sp[:22] + "…" if len(sp) > 22 else sp
            out.append(
                {
                    "task": task,
                    "attempts_total": int(atn or 0),
                    "completed_n": int(done_n or 0),
                    "awaiting_manager_pay": int(wait_n or 0),
                    "paid_by_manager": int(paid_n or 0),
                    "owner_label": owner,
                    "venue_city_short": vc,
                    "sphere_short": sp_short,
                }
            )
        return out


class ReferralRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def set_referrer_if_first_time(self, referee_user_id: int, referrer_user_id: int) -> bool:
        """
        Устанавливает referrer (уровень 1) только один раз — если у пользователя ещё нет записи.
        Возвращает True если связь создана.
        """
        if referrer_user_id == referee_user_id:
            return False

        existing = await self.get_referrer_for_referee(referee_user_id)
        if existing:
            return False

        self.session.add(Referral(referrer_user_id=referrer_user_id, referee_user_id=referee_user_id))
        await self.session.flush()
        return True

    async def get_referrer_for_referee(self, referee_user_id: int) -> int | None:
        result = await self.session.execute(
            select(Referral.referrer_user_id).where(Referral.referee_user_id == referee_user_id)
        )
        return result.scalar_one_or_none()

    async def get_total_referral_income(self, user_id: int) -> float:
        result = await self.session.execute(
            select(func.coalesce(func.sum(BalanceOperation.amount), 0)).where(
                BalanceOperation.user_id == user_id,
                BalanceOperation.operation_type.in_(
                    ["referral_commission_l1", "referral_commission_l2"]
                ),
            )
        )
        return float(result.scalar() or 0)
