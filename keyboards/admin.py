# -*- coding: utf-8 -*-
"""Клавиатуры админ-панели."""
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Управление заданиями", callback_data="admin:tasks")],
            [InlineKeyboardButton(text="📊 Аналитика и инструменты", callback_data="admin:analytics_hub")],
            [InlineKeyboardButton(text="✅ Допуск к заданиям", callback_data="admin:admission_queue")],
            [InlineKeyboardButton(text="📝 Подтверждение отзывов", callback_data="admin:reviews_queue")],
            [InlineKeyboardButton(text="🔎 ЛК пользователя", callback_data="admin:user_profile")],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats")],
            [InlineKeyboardButton(text="📢 Массовая рассылка", callback_data="admin:broadcast")],
            [InlineKeyboardButton(text="👤 Управление пользователями", callback_data="admin:users")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin:settings")],
            [InlineKeyboardButton(text="💸 Заявки на вывод", callback_data="admin:withdrawals")],
        ]
    )


def admin_back_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="◀ Назад", callback_data="admin:back_main")]]
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


def admin_analytics_hub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📌 Центр модерации", callback_data="admin:moderation_hub")],
            [InlineKeyboardButton(text="📤 Экспорт в CSV", callback_data="admin:export_menu")],
            [InlineKeyboardButton(text="📈 Задания: сводка", callback_data="admin:tasks_analytics_menu")],
            [InlineKeyboardButton(text="👔 Менеджеры: действия", callback_data="admin:manager_bulk_menu")],
            [InlineKeyboardButton(text="🤖 Статус бота", callback_data="admin:bot_status")],
            [InlineKeyboardButton(text="💾 Бэкап SQLite", callback_data="admin:db_backup")],
            [InlineKeyboardButton(text="◀ Назад", callback_data="admin:back_main")],
        ]
    )


def admin_moderation_hub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Обновить счётчики", callback_data="admin:moderation_hub_refresh")],
            [
                InlineKeyboardButton(text="✅ Допуск", callback_data="admin:admission_queue"),
                InlineKeyboardButton(text="📝 Отзывы", callback_data="admin:reviews_queue"),
            ],
            [
                InlineKeyboardButton(text="👤 2-й аккаунт", callback_data="admin:secacc_queue"),
                InlineKeyboardButton(text="💸 Выводы", callback_data="admin:withdrawals"),
            ],
            [InlineKeyboardButton(text="◀ К аналитике", callback_data="admin:analytics_hub")],
        ]
    )


def admin_export_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Попытки completed: 7 дн.", callback_data="admin:export:attempts:7")],
            [InlineKeyboardButton(text="Попытки completed: 30 дн.", callback_data="admin:export:attempts:30")],
            [InlineKeyboardButton(text="Попытки completed: 90 дн.", callback_data="admin:export:attempts:90")],
            [InlineKeyboardButton(text="Попытки: свои даты", callback_data="admin:export:attempts:custom")],
            [InlineKeyboardButton(text="Заявки на вывод: 7 дн.", callback_data="admin:export:wd:7")],
            [InlineKeyboardButton(text="Заявки на вывод: 30 дн.", callback_data="admin:export:wd:30")],
            [InlineKeyboardButton(text="Заявки на вывод: 90 дн.", callback_data="admin:export:wd:90")],
            [InlineKeyboardButton(text="Выводы: свои даты", callback_data="admin:export:wd:custom")],
            [InlineKeyboardButton(text="◀ К аналитике", callback_data="admin:analytics_hub")],
        ]
    )


def admin_tasks_analytics_root_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Все задания", callback_data="admin:tan:all")],
            [InlineKeyboardButton(text="Только админ", callback_data="admin:tan:admin")],
            [InlineKeyboardButton(text="Выбрать менеджера…", callback_data="admin:tan:pick_mgr")],
            [InlineKeyboardButton(text="◀ К аналитике", callback_data="admin:analytics_hub")],
        ]
    )
