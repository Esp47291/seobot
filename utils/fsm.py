# -*- coding: utf-8 -*-
"""FSM для пользователя и админа."""

from aiogram.fsm.state import State, StatesGroup


class UserFSM(StatesGroup):
    """Состояния пользователя: обучение, ожидание скрина и реквизитов."""

    training_step = State()
    waiting_screenshot = State()
    waiting_payment_details = State()


class AdminFSM(StatesGroup):
    """Состояния админа: ввод username и текста для рассылки."""

    waiting_username = State()
    waiting_message = State()
