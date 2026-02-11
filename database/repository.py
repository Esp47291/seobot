# -*- coding: utf-8 -*-
"""Репозитории для работы с БД."""

from datetime import datetime, timedelta
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import User, Link, ReviewText, TrainingMessage, Task, AdminAction
from config import YANDEX_COOLDOWN_HOURS, TWOGIS_COOLDOWN_HOURS, TRAINING_STEPS


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_user_id(self, user_id: int) -> User | None:
        r = await self.session.execute(select(User).where(User.user_id == user_id))
        return r.scalar_one_or_none()

    async def get_or_create(
        self,
        user_id: int,
        username: str | None = None,
        first_name: str | None = None,
    ) -> User:
        user = await self.get_by_user_id(user_id)
        if user:
            if username is not None:
                user.username = username
            if first_name is not None:
                user.first_name = first_name
            await self.session.flush()
            return user
        user = User(
            user_id=user_id,
            username=username,
            first_name=first_name,
        )
        self.session.add(user)
        await self.session.flush()
        return user

    async def update_last_review(self, user_id: int, platform: str) -> None:
        now = datetime.utcnow()
        stmt = (
            update(User)
            .where(User.user_id == user_id)
            .values(
                last_yandex_review=now if platform == "yandex" else User.last_yandex_review,
                last_2gis_review=now if platform == "2gis" else User.last_2gis_review,
            )
        )
        await self.session.execute(stmt)

    async def get_by_username(self, username: str) -> User | None:
        name = username.lstrip("@")
        r = await self.session.execute(select(User).where(User.username == name))
        return r.scalar_one_or_none()


class LinkRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_by_platform(self, platform: str):
        r = await self.session.execute(
            select(Link).where(and_(Link.platform == platform, Link.is_active == True))
        )
        return list(r.scalars().all())

    async def get_by_id(self, link_id: int) -> Link | None:
        r = await self.session.execute(select(Link).where(Link.id == link_id))
        return r.scalar_one_or_none()

    async def get_by_url(self, url: str) -> Link | None:
        r = await self.session.execute(select(Link).where(Link.url == url))
        return r.scalar_one_or_none()

    async def create(self, platform: str, url: str) -> Link:
        link = Link(platform=platform, url=url)
        self.session.add(link)
        await self.session.flush()
        return link

    async def set_active(self, link_id: int, is_active: bool) -> None:
        await self.session.execute(update(Link).where(Link.id == link_id).values(is_active=is_active))

    async def get_all(self):
        r = await self.session.execute(select(Link).order_by(Link.id))
        return list(r.scalars().all())


class ReviewTextRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_active_by_link_id(self, link_id: int):
        r = await self.session.execute(
            select(ReviewText).where(
                and_(ReviewText.link_id == link_id, ReviewText.is_active == True)
            )
        )
        return list(r.scalars().all())

    async def get_by_id(self, text_id: int) -> ReviewText | None:
        r = await self.session.execute(select(ReviewText).where(ReviewText.id == text_id))
        return r.scalar_one_or_none()

    async def create(self, link_id: int, text: str) -> ReviewText:
        rt = ReviewText(link_id=link_id, text=text)
        self.session.add(rt)
        await self.session.flush()
        return rt

    async def set_active(self, text_id: int, is_active: bool) -> None:
        await self.session.execute(
            update(ReviewText).where(ReviewText.id == text_id).values(is_active=is_active)
        )


class TrainingMessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_step(self, step_number: int) -> TrainingMessage | None:
        r = await self.session.execute(
            select(TrainingMessage).where(TrainingMessage.step_number == step_number)
        )
        return r.scalar_one_or_none()

    async def get_all_ordered(self):
        r = await self.session.execute(
            select(TrainingMessage).order_by(TrainingMessage.step_number)
        )
        return list(r.scalars().all())

    async def set_text(self, step_number: int, text: str) -> TrainingMessage:
        msg = await self.get_by_step(step_number)
        if msg:
            msg.text = text
            await self.session.flush()
            return msg
        msg = TrainingMessage(step_number=step_number, text=text)
        self.session.add(msg)
        await self.session.flush()
        return msg

    async def ensure_steps_exist(self) -> None:
        for step in range(1, TRAINING_STEPS + 1):
            if await self.get_by_step(step) is None:
                self.session.add(
                    TrainingMessage(step_number=step, text=f"Шаг обучения {step}. Отредактируйте в админке.")
                )
        await self.session.flush()


class TaskRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        link_id: int,
        text_id: int | None,
    ) -> Task:
        task = Task(user_id=user_id, link_id=link_id, text_id=text_id, status="pending")
        self.session.add(task)
        await self.session.flush()
        return task

    async def get_last_pending_by_user(self, user_id: int) -> Task | None:
        r = await self.session.execute(
            select(Task)
            .where(and_(Task.user_id == user_id, Task.status == "pending"))
            .order_by(Task.created_at.desc())
            .limit(1)
            .options(
                selectinload(Task.link),
                selectinload(Task.review_text),
            )
        )
        return r.scalar_one_or_none()

    async def get_by_id(self, task_id: int) -> Task | None:
        r = await self.session.execute(
            select(Task)
            .where(Task.id == task_id)
            .options(
                selectinload(Task.user),
                selectinload(Task.link),
                selectinload(Task.review_text),
            )
        )
        return r.scalar_one_or_none()

    async def get_pending(self):
        r = await self.session.execute(
            select(Task)
            .where(Task.status == "pending")
            .order_by(Task.created_at.desc())
            .options(
                selectinload(Task.user),
                selectinload(Task.link),
                selectinload(Task.review_text),
            )
        )
        return list(r.unique().scalars().all())

    async def get_approved_unpaid(self):
        r = await self.session.execute(
            select(Task)
            .where(Task.status == "approved")
            .order_by(Task.approved_at.desc())
            .options(
                selectinload(Task.user),
                selectinload(Task.link),
                selectinload(Task.review_text),
            )
        )
        return list(r.unique().scalars().all())

    async def approve(self, task_id: int) -> Task | None:
        task = await self.get_by_id(task_id)
        if not task or task.status != "pending":
            return None
        task.status = "approved"
        task.approved_at = datetime.utcnow()
        await self.session.flush()
        return task

    async def reject(self, task_id: int) -> Task | None:
        task = await self.get_by_id(task_id)
        if not task or task.status != "pending":
            return None
        task.status = "rejected"
        await self.session.flush()
        return task

    async def mark_paid(self, task_id: int) -> Task | None:
        task = await self.get_by_id(task_id)
        if not task or task.status != "approved":
            return None
        task.status = "paid"
        task.paid_at = datetime.utcnow()
        await self.session.flush()
        return task

    async def update_submission(self, task_id: int, screenshot_file_id: str, payment_details: str) -> Task | None:
        task = await self.get_by_id(task_id)
        if not task or task.status != "pending":
            return None
        task.screenshot_file_id = screenshot_file_id
        task.payment_details = payment_details
        await self.session.flush()
        return task

    def can_take_task(self, last_review: datetime | None, platform: str) -> bool:
        if last_review is None:
            return True
        hours = YANDEX_COOLDOWN_HOURS if platform == "yandex" else TWOGIS_COOLDOWN_HOURS
        return datetime.utcnow() - last_review >= timedelta(hours=hours)


class AdminActionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def log(self, admin_id: int, action_type: str, target_id: int | None = None) -> None:
        self.session.add(
            AdminAction(admin_id=admin_id, action_type=action_type, target_id=target_id)
        )
        await self.session.flush()
