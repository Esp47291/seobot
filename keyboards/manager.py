# -*- coding: utf-8 -*-
"""Клавиатуры панели менеджера (/manager)."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def manager_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Мои задания", callback_data="mgr:tasks")],
            [InlineKeyboardButton(text="📈 Аналитика по заданиям", callback_data="mgr:tasks_analytics")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="mgr:stats")],
            [InlineKeyboardButton(text="✉️ Личная рассылка", callback_data="mgr:broadcast")],
            [InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="mgr:withdrawals")],
        ]
    )


def manager_withdraw_kb(withdraw_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Выплачено", callback_data=f"mgr:wd_paid:{withdraw_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"mgr:wd_rej:{withdraw_id}"),
            ]
        ]
    )


def manager_payout_kb(attempt_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", callback_data=f"mgr:outpay:{attempt_id}")]
        ]
    )
