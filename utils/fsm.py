# -*- coding: utf-8 -*-
"""FSM для пользователя и админа."""

from aiogram.fsm.state import State, StatesGroup


class UserFSM(StatesGroup):
    choosing_city = State()
    choosing_platform = State()
    waiting_account_screenshot = State()
    waiting_review_screenshot = State()
    waiting_withdraw_amount = State()
    waiting_withdraw_requisites = State()


class AdminFSM(StatesGroup):
    waiting_decline_reason = State()
    waiting_reject_reason = State()
    # Добавление задания (inline-поток)
    waiting_task_platform = State()  # шаг 1
    waiting_task_price = State()  # шаг 2
    waiting_task_instruction = State()  # шаг 3
    waiting_task_venue_link = State()  # шаг 4
    waiting_broadcast_content = State()
    waiting_target_user = State()
    waiting_user_query = State()
    waiting_balance_change = State()  # ввод команды /balance +100 <id|@username>
    waiting_settings_value = State()
