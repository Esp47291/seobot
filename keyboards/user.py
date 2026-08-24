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


def tasks_all_done_kb() -> InlineKeyboardMarkup:
    """Когда по платформе все задания уже выполнены — второй аккаунт или назад."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="У меня есть второй аккаунт", callback_data="secacc:want")],
            [InlineKeyboardButton(text="◀ К выбору города", callback_data="back_task_venue")],
        ]
    )


def task_venue_cities_kb(pick_list: list[str], empty_marker: str) -> InlineKeyboardMarkup:
    """Города организаций (venue_city); empty_marker — служебное значение для заданий без города."""
    rows: list[list[InlineKeyboardButton]] = []
    for i, label in enumerate(pick_list):
        btn_text = "📍 Другие (город не указан)" if label == empty_marker else label
        if len(btn_text) > 64:
            btn_text = btn_text[:61] + "…"
        rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"taskvenue:{i}")])
    rows.append([InlineKeyboardButton(text="🔙 В главное меню", callback_data="to_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def platforms_kb(platforms: list[str], *, show_back_venue: bool = False) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=p, callback_data=f"platform:{p}")] for p in platforms]
    if show_back_venue:
        rows.append([InlineKeyboardButton(text="◀ Выбор города", callback_data="back_task_venue")])
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
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 История отзывов", callback_data="cabinet_reviews")],
            [InlineKeyboardButton(text="📊 История операций", callback_data="cabinet_history")],
            [InlineKeyboardButton(text="✏️ Редактировать реквизиты", callback_data="cabinet_edit_requisites")],
            [InlineKeyboardButton(text="◀️ В главное меню", callback_data="to_menu")],
        ]
    )


def cabinet_back_kb() -> InlineKeyboardMarkup:
    """Назад в экран личного кабинета (баланс и кнопки)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="◀ Назад", callback_data="cabinet_back")],
        ]
    )


def cabinet_reviews_nav_kb(page: int, total_pages: int) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if total_pages > 1:
        nav: list[InlineKeyboardButton] = []
        if page > 0:
            nav.append(InlineKeyboardButton(text="◀ Раньше", callback_data=f"cabinet_reviews:{page - 1}"))
        if page < total_pages - 1:
            nav.append(InlineKeyboardButton(text="Позже ▶", callback_data=f"cabinet_reviews:{page + 1}"))
        if nav:
            rows.append(nav)
    rows.append([InlineKeyboardButton(text="◀ Назад", callback_data="cabinet_back")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
