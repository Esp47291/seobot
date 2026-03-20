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
# ID менеджеров (через запятую): MANAGER_IDS=111,222
MANAGER_IDS: list[int] = _parse_admin_ids(env.str("MANAGER_IDS", ""))
SUPPORT_URL: str = env.str("SUPPORT_URL", "https://t.me/")
PROXY_URL: str = env.str("PROXY_URL", "")

# Если PROXY_URL не задан в .env, попробуем взять из переменных окружения.
# Примеры:
# HTTP_PROXY=http://127.0.0.1:8888
# HTTPS_PROXY=http://127.0.0.1:8888
if not PROXY_URL:
    PROXY_URL = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy") or ""
if not PROXY_URL:
    PROXY_URL = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "seobot.db")
DATABASE_URL: str = env.str("DATABASE_URL", f"sqlite+aiosqlite:///{DB_PATH}")

DEFAULT_MIN_WITHDRAW: int = env.int("DEFAULT_MIN_WITHDRAW", 20)
# Текст для админа: рекомендуемый срок «живой» проверки отзыва на площадке
REVIEW_CHECK_DAYS: int = env.int("REVIEW_CHECK_DAYS", 3)
# Через сколько минут после скрина отзыва бот пришлёт админу напоминание с кнопками Принять/Отклонить
REVIEW_REMINDER_AFTER_MINUTES: int = env.int("REVIEW_REMINDER_AFTER_MINUTES", 1)
# Как часто джоб проверяет просроченные отзывы (для REMINDER=1 поставьте 1)
REVIEW_SCHEDULER_INTERVAL_MINUTES: int = env.int("REVIEW_SCHEDULER_INTERVAL_MINUTES", 1)
SCHEDULER_INTERVAL_MINUTES: int = env.int("SCHEDULER_INTERVAL_MINUTES", 60)
