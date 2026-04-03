# -*- coding: utf-8 -*-
"""FSM для пользователя и админа."""

from aiogram.fsm.state import State, StatesGroup


class UserFSM(StatesGroup):
    choosing_city = State()  # устар.: ввод города в профиль (если останется отдельный сценарий)
    choosing_venue_city = State()  # город организаций с заданиями (до выбора платформы)
    choosing_platform = State()
    waiting_account_screenshot = State()
    waiting_review_screenshot = State()
    waiting_profile_requisites = State()
    waiting_second_account_screenshot = State()
    waiting_withdraw_amount = State()
    waiting_withdraw_requisites = State()


class ManagerFSM(StatesGroup):
    """FSM панели менеджера (отдельно от админа, чтобы состояния не пересекались)."""
    waiting_task_platform = State()
    waiting_task_price = State()
    waiting_task_venue_city = State()
    waiting_task_sphere = State()
    waiting_task_instruction = State()
    waiting_task_prebuilt_mode = State()  # шаг 6: готовые тексты / без них
    waiting_task_prebuilt_texts = State()  # шаг 6: ввод готовых текстов (по 1 сообщению)
    waiting_task_daily_custom = State()  # шаг 7: ввод своего числа (1..10)
    waiting_task_venue_link = State()  # шаг 8: ссылка
    waiting_broadcast_content = State()


class AdminFSM(StatesGroup):
    waiting_decline_reason = State()
    waiting_reject_reason = State()
    # Добавление задания (inline-поток)
    waiting_task_platform = State()  # шаг 1
    waiting_task_price = State()  # шаг 2
    waiting_task_venue_city = State()  # шаг 3 — город организации для карточки
    waiting_task_sphere = State()  # шаг 4 — сфера для карточки
    waiting_task_instruction = State()  # шаг 5
    waiting_task_prebuilt_mode = State()  # шаг 6: готовые тексты / без них
    waiting_task_prebuilt_texts = State()  # шаг 6: ввод готовых текстов (по 1 сообщению)
    waiting_task_daily_custom = State()  # шаг 7: ввод своего числа (1..10)
    waiting_task_venue_link = State()  # шаг 8: ссылка
    waiting_broadcast_content = State()
    waiting_target_user = State()
    waiting_user_query = State()
    waiting_balance_change = State()  # ввод команды /balance +100 <id|@username>
    waiting_settings_value = State()
    waiting_export_date_from = State()
    waiting_export_date_to = State()
