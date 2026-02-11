# -*- coding: utf-8 -*-
"""Модели SQLAlchemy для всех таблиц."""

from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    String,
    Text,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    last_yandex_review: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_2gis_review: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="user")


class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(20))  # yandex / 2gis
    url: Mapped[str] = mapped_column(String(1024), unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    review_texts: Mapped[list["ReviewText"]] = relationship(
        "ReviewText", back_populates="link", cascade="all, delete-orphan"
    )
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="link")


class ReviewText(Base):
    __tablename__ = "review_texts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    link: Mapped["Link"] = relationship("Link", back_populates="review_texts")
    tasks: Mapped[list["Task"]] = relationship("Task", back_populates="review_text")


class TrainingMessage(Base):
    __tablename__ = "training_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    step_number: Mapped[int] = mapped_column(Integer, unique=True)  # 1-4
    text: Mapped[str] = mapped_column(Text)

    def __repr__(self):
        return f"<TrainingMessage step={self.step_number}>"


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"))
    link_id: Mapped[int] = mapped_column(ForeignKey("links.id", ondelete="CASCADE"))
    text_id: Mapped[int] = mapped_column(ForeignKey("review_texts.id", ondelete="SET NULL"), nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # pending, approved, paid, rejected
    screenshot_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="tasks")
    link: Mapped["Link"] = relationship("Link", back_populates="tasks")
    review_text: Mapped["ReviewText | None"] = relationship("ReviewText", back_populates="tasks")


class AdminAction(Base):
    __tablename__ = "admin_actions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    action_type: Mapped[str] = mapped_column(String(50))
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
