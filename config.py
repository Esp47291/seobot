# -*- coding: utf-8 -*-
"""Конфигурация бота через переменные окружения."""
import os

from environs import Env

env = Env()
env.read_env()


def _parse_admin_ids(value: str) -> list[int]:
    if not value or not value.strip():
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()]


BOT_TOKEN: str = env.str("BOT_TOKEN", "")
ADMIN_IDS: list[int] = _parse_admin_ids(env.str("ADMIN_IDS", ""))
SUPPORT_URL: str = env.str("SUPPORT_URL", "https://t.me/")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "seobot.db")
DATABASE_URL: str = env.str("DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH}")

DEFAULT_MIN_WITHDRAW: int = env.int("DEFAULT_MIN_WITHDRAW", 20)
REVIEW_CHECK_DAYS: int = env.int("REVIEW_CHECK_DAYS", 3)
SCHEDULER_INTERVAL_MINUTES: int = env.int("SCHEDULER_INTERVAL_MINUTES", 60)
