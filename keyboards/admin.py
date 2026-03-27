# -*- coding: utf-8 -*-
"""Клавиатуры админ-панели."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Управление заданиями", callback_data="admin:tasks")],
            [InlineKeyboardButton(text="✅ Допуск к заданиям", callback_data="admin:admission_queue")],
            [InlineKeyboardButton(text="📝 Подтверждение отзывов", callback_data="admin:reviews_queue")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="📢 Массовая рассылка", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="👤 Управление пользователями", callback_data="admin:users")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin:settings")],
            [InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="admin:withdrawals")],
        ]
    )


def second_account_moderation_kb(review_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Принять", callback_data=f"admin:secacc_ok:{review_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin:secacc_reject:{review_id}"),
            ]
        ]
    )


def moderation_kb(attempt_id: int, stage: str) -> InlineKeyboardMarkup:
    if stage == "pre":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Допустить", callback_data=f"admin:allow:{attempt_id}"),
                    InlineKeyboardButton(text="❌ Отказать", callback_data=f"admin:decline:{attempt_id}"),
                ]
            ]
        )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Отзыв принят", callback_data=f"admin:review_ok:{attempt_id}"),
                InlineKeyboardButton(text="❌ Отзыв отклонен", callback_data=f"admin:review_bad:{attempt_id}"),
            ]
        ]
    )


def withdraw_kb(withdraw_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выплачено", callback_data=f"admin:wd_paid:{withdraw_id}"),
                InlineKeyboardButton(text="❌ Отклонить заявку", callback_data=f"admin:wd_rej:{withdraw_id}"),
            ]
        ]
    )


def users_manage_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔒 Заблокировать", callback_data="admin:user_block")],
            [InlineKeyboardButton(text="🔓 Разблокировать", callback_data="admin:user_unblock")],
            [InlineKeyboardButton(text="💰 Добавить баланс", callback_data="admin:user_balance_add")],
            [InlineKeyboardButton(text="💸 Уменьшить баланс", callback_data="admin:user_balance_sub")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="admin:back_main")],
        ]
    )
