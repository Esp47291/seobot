# -*- coding: utf-8 -*-
"""Общие текстовые команды настроек для админов и менеджеров."""
from aiogram import F, Router
from aiogram.types import Message

from database import SettingsRepository

router = Router(name="staff_settings")


@router.message(F.text.startswith("set_welcome "))
async def set_welcome(message: Message, **data):
    payload = message.text[len("set_welcome ") :].strip()
    await SettingsRepository(data["session"]).set_field("welcome_text", payload)
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_help "))
async def set_help(message: Message, **data):
    payload = message.text[len("set_help ") :].strip()
    await SettingsRepository(data["session"]).set_field("help_text", payload)
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_min_withdraw "))
async def set_min_withdraw(message: Message, **data):
    await SettingsRepository(data["session"]).set_field("min_withdraw_amount", int(message.text.split()[1]))
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_min_review_yandex "))
async def set_min_review_yandex(message: Message, **data):
    await SettingsRepository(data["session"]).set_field(
        "min_review_price_yandex", int(message.text.split(maxsplit=1)[1])
    )
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_min_review_google "))
async def set_min_review_google(message: Message, **data):
    await SettingsRepository(data["session"]).set_field(
        "min_review_price_google", int(message.text.split(maxsplit=1)[1])
    )
    await message.answer("Обновлено.")


@router.message(F.text.startswith("set_min_review_2gis "))
async def set_min_review_2gis(message: Message, **data):
    await SettingsRepository(data["session"]).set_field(
        "min_review_price_2gis", int(message.text.split(maxsplit=1)[1])
    )
    await message.answer("Обновлено.")
