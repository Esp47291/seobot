# -*- coding: utf-8 -*-
"""Клавиатуры для админ-панели."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

ADMIN_BACK = "admin_back"
ADMIN_UNVERIFIED = "admin_unverified"
ADMIN_APPROVED_UNPAID = "admin_approved_unpaid"
ADMIN_LINKS = "admin_links"
ADMIN_TRAINING = "admin_training"
ADMIN_WRITE_USER = "admin_write_user"
ADMIN_TASK = "admin_task:"
ADMIN_APPROVE = "admin_approve:"
ADMIN_REJECT = "admin_reject:"
ADMIN_PAID = "admin_paid:"
ADMIN_LINK_ADD = "admin_link_add"
ADMIN_LINK_LIST = "admin_link_list"
ADMIN_TRAINING_EDIT = "admin_training_edit:"


def kb_admin_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Непроверенные отзывы", callback_data=ADMIN_UNVERIFIED)],
            [InlineKeyboardButton(text="💰 Подтверждённые, не оплаченные", callback_data=ADMIN_APPROVED_UNPAID)],
            [InlineKeyboardButton(text="🔗 Управление ссылками", callback_data=ADMIN_LINKS)],
            [InlineKeyboardButton(text="📚 Редактировать обучение", callback_data=ADMIN_TRAINING)],
            [InlineKeyboardButton(text="✉️ Написать пользователю", callback_data=ADMIN_WRITE_USER)],
        ]
    )


def kb_admin_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data=ADMIN_BACK)]
        ]
    )


def kb_task_approve_reject(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"{ADMIN_APPROVE}{task_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"{ADMIN_REJECT}{task_id}"),
            ],
            [InlineKeyboardButton(text="◀ К списку", callback_data=ADMIN_UNVERIFIED)],
        ]
    )


def kb_task_paid(task_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💰 Выплачено", callback_data=f"{ADMIN_PAID}{task_id}")],
            [InlineKeyboardButton(text="◀ Назад", callback_data=ADMIN_APPROVED_UNPAID)],
        ]
    )


def kb_links_manage() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить ссылку", callback_data=ADMIN_LINK_ADD)],
            [InlineKeyboardButton(text="📄 Список ссылок", callback_data=ADMIN_LINK_LIST)],
            [InlineKeyboardButton(text="◀ Назад", callback_data=ADMIN_BACK)],
        ]
    )


def kb_edit_training_step(step: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data=ADMIN_TRAINING)]
        ]
    )


def kb_task_item(task_id: int, label: str, prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label, callback_data=f"{prefix}{task_id}")]
        ]
    )
