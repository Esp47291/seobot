# -*- coding: utf-8 -*-
"""Клавиатуры для пользователя."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

BTN_NEXT = "Далее ▶"
BTN_TAKE_TASK = "Взять задание"
BTN_SENT_REVIEW = "Я написал отзыв, отправить на проверку"
CALLBACK_NEXT = "training_next"
CALLBACK_TAKE = "take_task"
CALLBACK_SENT = "sent_review"


def kb_next_training(step: int, total: int) -> InlineKeyboardMarkup:
    if step >= total:
        return InlineKeyboardMarkup(inline_keyboard=[])
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_NEXT, callback_data=f"{CALLBACK_NEXT}:{step}")]
        ]
    )


def kb_after_training() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_TAKE_TASK, callback_data=CALLBACK_TAKE)]
        ]
    )


def kb_take_task() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_TAKE_TASK, callback_data=CALLBACK_TAKE)]
        ]
    )


def kb_sent_for_review() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=BTN_SENT_REVIEW, callback_data=CALLBACK_SENT)]
        ]
    )


def kb_copy_text() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Копировать текст", callback_data="copy_text")]
        ]
    )
