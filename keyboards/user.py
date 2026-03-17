# -*- coding: utf-8 -*-
"""Клавиатуры пользовательской части."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✍️ Приступить к заданию")],
            [KeyboardButton(text="💰 Личный кабинет / Баланс"), KeyboardButton(text="💸 Вывести средства")],
            [KeyboardButton(text="👥 Реферальная программа"), KeyboardButton(text="🆘 Помощь")],
        ],
        resize_keyboard=True,
    )


def platforms_kb(platforms: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=p, callback_data=f"platform:{p}")] for p in platforms]
    rows.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def task_card_kb(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Начать задание", callback_data=f"start_task:{task_id}")],
            [InlineKeyboardButton(text="🔜 Следующее задание", callback_data=f"next_task:{task_id}")],
            [InlineKeyboardButton(text="🚫 Не интересно", callback_data=f"skip_task:{task_id}")],
            [InlineKeyboardButton(text="🔙 В главное меню", callback_data="to_menu")],
        ]
    )


def cancel_attempt_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🔙 Отменить и в меню", callback_data="cancel_attempt")]]
    )


def operations_history_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="📊 История операций", callback_data="cabinet_history")]]
    )
