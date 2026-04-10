# -*- coding: utf-8 -*-
"""Модели SQLAlchemy для SeoJob / Отзовик."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Реквизиты для выплат за задания (редактируются в ЛК)
    payout_requisites: Mapped[str | None] = mapped_column(Text, nullable=True)
    balance: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)
    registered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # JSON: платформа -> последний task_item_id (честная ротация карточек)
    task_rotation_json: Mapped[str] = mapped_column(Text, default="{}")
    # JSON: платформа -> true — после проверки «2-й аккаунт» можно снова брать задания (сбрасывается после нового completed)
    repeat_unlock_json: Mapped[str] = mapped_column(Text, default="{}")

    # Согласие с правилами перед доступом к функционалу бота.
    rules_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    # Чтобы не отправлять полное сообщение с правилами много раз.
    rules_prompted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Согласие на допуск через подписку на новостной канал.
    # Это не реальная проверка подписки — пользователь сам подтверждает кнопкой.
    news_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    news_prompted: Mapped[bool] = mapped_column(Boolean, default=False)


class SecondAccountReview(Base):
    """Модерация скрина второго аккаунта на площадке (чтобы снова брать задания по платформе)."""

    __tablename__ = "second_account_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    platform: Mapped[str] = mapped_column(String(120))
    screenshot_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TaskItem(Base):
    __tablename__ = "task_items"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String(50), index=True)
    # Фильтр показа исполнителям: "*" = все города, иначе совпадение с городом в профиле
    city: Mapped[str] = mapped_column(String(255), index=True)
    # Город организации / заведения — показывается исполнителю на карточке
    venue_city: Mapped[str] = mapped_column(String(255), default="")
    sphere: Mapped[str] = mapped_column(String(255))
    instruction_url: Mapped[str] = mapped_column(String(1024))
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    # Сколько раз за день выдавать это задание. None = не ограничивать (для старых задач).
    daily_issue_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Готовые тексты отзыва (по одному исполнителю). JSON-массив строк.
    prebuilt_texts_json: Mapped[str] = mapped_column(Text, default="[]")
    # Индекс следующего текста для выдачи.
    prebuilt_text_cursor: Mapped[int] = mapped_column(Integer, default=0)
    # Чтобы не спамить уведомлением менеджеру/админу после окончания текстов.
    prebuilt_texts_exhausted_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    # Telegram user_id менеджера, разместившего задание; NULL = задание админа
    created_by_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)


class Attempt(Base):
    __tablename__ = "attempts"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    task_item_id: Mapped[int] = mapped_column(ForeignKey("task_items.id", ondelete="CASCADE"), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    account_screenshot_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    review_screenshot_file_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    decline_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    check_after: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    review_check_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    payout_requisites: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Для заданий менеджера: баланс начисляется после нажатия «Оплатил»
    balance_credited: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WithdrawalRequest(Base):
    __tablename__ = "withdrawal_requests"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    requisites: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class BalanceOperation(Base):
    __tablename__ = "balance_operations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.user_id", ondelete="CASCADE"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(10, 2))
    operation_type: Mapped[str] = mapped_column(String(32))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class BotSetting(Base):
    __tablename__ = "bot_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    welcome_text: Mapped[str] = mapped_column(
        Text,
        default=(
            "Добро пожаловать в Job Inside!\n\n"
            "Выберите действие в меню ниже — и начнем зарабатывать.\n\n"
            "✍️ Приступить к заданию\n"
            "💰 Личный кабинет / Баланс\n"
            "💸 Вывести средства\n"
            "👥 Реферальная программа\n"
            "🆘 Помощь"
        ),
    )
    help_text: Mapped[str] = mapped_column(
        Text,
        default="Поддержка: напишите в чат поддержки.",
    )
    min_withdraw_amount: Mapped[int] = mapped_column(Integer, default=20)

    # Минимальная оплата за отзыв по платформам
    min_review_price_yandex: Mapped[int] = mapped_column(Integer, default=130)
    min_review_price_google: Mapped[int] = mapped_column(Integer, default=35)
    min_review_price_2gis: Mapped[int] = mapped_column(Integer, default=12)

    # Через сколько часов после завершения/оплаты отзыва напомнить исполнителю, что снова можно взять задание
    reminder_hours_yandex: Mapped[int] = mapped_column(Integer, default=60)
    reminder_hours_2gis: Mapped[int] = mapped_column(Integer, default=24)
    reminder_hours_google: Mapped[int] = mapped_column(Integer, default=24)
    reminder_hours_other: Mapped[int] = mapped_column(Integer, default=24)


class ExecutorRepeatReminder(Base):
    """Очередь напоминаний исполнителю о возможности снова взять задание на платформе."""

    __tablename__ = "executor_repeat_reminders"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    platform: Mapped[str] = mapped_column(String(120))
    remind_at: Mapped[datetime] = mapped_column(DateTime, index=True)
    sent: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Referral(Base):
    """
    Связь реферала 1 уровня:
    - referrer_user_id: кто пригласил
    - referee_user_id: приглашенный (становится рефералом 1 уровня навсегда)
    """

    __tablename__ = "referrals"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    referrer_user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    referee_user_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
