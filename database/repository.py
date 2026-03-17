# -*- coding: utf-8 -*-
"""Репозитории для SeoJob / Отзовик."""
from datetime import datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import DEFAULT_MIN_WITHDRAW, REVIEW_CHECK_DAYS
from .models import Attempt, BalanceOperation, BotSetting, TaskItem, User, WithdrawalRequest


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create(self, user_id: int, username: str | None, first_name: str | None) -> User:
        user = await self.get_by_user_id(user_id)
        if user:
            user.username = username
            user.first_name = first_name
            await self.session.flush()
            return user
        user = User(user_id=user_id, username=username, first_name=first_name)
        self.session.add(user)
        await self.session.flush()
        return user

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


class TaskItemRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_platforms_by_city(self, city: str) -> list[str]:
        result = await self.session.execute(
            select(TaskItem.platform)
            .where(TaskItem.city == city, TaskItem.is_active == True)
            .group_by(TaskItem.platform)
            .order_by(TaskItem.platform)
        )
        return list(result.scalars().all())

    async def get_active_for_city_platform(self, city: str, platform: str) -> list[TaskItem]:
        result = await self.session.execute(
            select(TaskItem)
            .where(TaskItem.city == city, TaskItem.platform == platform, TaskItem.is_active == True)
            .order_by(TaskItem.id)
        )
        return list(result.scalars().all())

    async def get_by_id(self, task_item_id: int) -> TaskItem | None:
        result = await self.session.execute(select(TaskItem).where(TaskItem.id == task_item_id))
        return result.scalar_one_or_none()

    async def get_all(self) -> list[TaskItem]:
        result = await self.session.execute(select(TaskItem).order_by(TaskItem.id.desc()))
        return list(result.scalars().all())

    async def create(self, platform: str, city: str, sphere: str, price: float, instruction_url: str) -> TaskItem:
        task = TaskItem(platform=platform, city=city, sphere=sphere, price=price, instruction_url=instruction_url)
        self.session.add(task)
        await self.session.flush()
        return task

    async def update_field(self, task_item_id: int, field_name: str, value: str) -> bool:
        task = await self.get_by_id(task_item_id)
        if not task or not hasattr(task, field_name):
            return False
        if field_name == "price":
            setattr(task, field_name, Decimal(value))
        else:
            setattr(task, field_name, value)
        await self.session.flush()
        return True

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


class AttemptRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user_id: int, task_item_id: int) -> Attempt:
        attempt = Attempt(user_id=user_id, task_item_id=task_item_id, status="waiting_approval")
        self.session.add(attempt)
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

    async def set_account_screenshot(self, attempt_id: int, file_id: str) -> None:
        attempt = await self.get_by_id(attempt_id)
        if attempt:
            attempt.account_screenshot_file_id = file_id
            attempt.status = "login_screenshot"
            await self.session.flush()

    async def approve(self, attempt_id: int) -> Attempt | None:
        attempt = await self.get_by_id(attempt_id)
        if attempt:
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

    async def submit_review(self, attempt_id: int, file_id: str) -> Attempt | None:
        attempt = await self.get_by_id(attempt_id)
        if not attempt:
            return None
        attempt.review_screenshot_file_id = file_id
        attempt.status = "review_submitted"
        attempt.submitted_at = datetime.utcnow()
        attempt.check_after = attempt.submitted_at + timedelta(days=REVIEW_CHECK_DAYS)
        await self.session.flush()
        return attempt

    async def complete(self, attempt_id: int) -> Attempt | None:
        attempt = await self.get_by_id(attempt_id)
        if attempt:
            attempt.status = "completed"
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

    async def mark_review_check_requested(self, attempt_id: int) -> None:
        attempt = await self.get_by_id(attempt_id)
        if attempt:
            attempt.review_check_requested = True
            await self.session.flush()

    async def completed_count_by_user(self, user_id: int) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Attempt).where(Attempt.user_id == user_id, Attempt.status == "completed")
        )
        return int(result.scalar() or 0)


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
            return item
        item = BotSetting(id=1, min_withdraw_amount=DEFAULT_MIN_WITHDRAW)
        self.session.add(item)
        await self.session.flush()
        return item

    async def set_field(self, field_name: str, value) -> None:
        item = await self.get()
        setattr(item, field_name, value)
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
