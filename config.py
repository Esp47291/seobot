# -*- coding: utf-8 -*-
"""Конфигурация бота через переменные окружения."""
import os
from typing import Optional

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
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "seobot.db")


def _is_probably_netlify() -> bool:
    # Netlify обычно выставляет переменные NETLIFY* и при этом во время "build" часть ФС read-only.
    return bool(os.environ.get("NETLIFY") or os.environ.get("NETLIFY_BUILD_ID") or os.environ.get("NETLIFY_SITE_ID"))


def _default_sqlite_db_path() -> str:
    if _is_probably_netlify():
        return "/tmp/seobot.db"

    # На VPS используем папку проекта, но если нет прав - fallback на /tmp.
    try:
        os.makedirs(os.path.dirname(DEFAULT_DB_PATH), exist_ok=True)
        return DEFAULT_DB_PATH
    except Exception:
        return "/tmp/seobot.db"


def sqlite_db_file_path_from_url(database_url: str) -> Optional[str]:
    """
    Возвращает путь к файлу SQLite из DATABASE_URL (только для файловых БД).
    Для :memory: вернёт None.
    """
    url = (database_url or "").split("?", 1)[0]
    if not url.startswith("sqlite"):
        return None
    if ":memory:" in url:
        return None

    # Примеры:
    # sqlite+aiosqlite:///./data.db        -> ./data.db
    # sqlite+aiosqlite:////tmp/x.db        -> /tmp/x.db
    prefixes = (
        "sqlite+aiosqlite:////",
        "sqlite:////",
        "sqlite+aiosqlite:///",
        "sqlite:///",
    )
    for p in prefixes:
        if url.startswith(p):
            rest = url[len(p) :]
            if p.endswith("////"):
                return "/" + rest
            return rest
    return None


# DB_PATH оставляем для совместимости (используется, например, в старом коде),
# но при необходимости путь берём из фактического DATABASE_URL.
DB_PATH = DEFAULT_DB_PATH

# Если DATABASE_URL передан явно - используем его целиком.
# Иначе формируем дефолт с учетом окружения (например, Netlify build).
_env_database_url = env.str("DATABASE_URL", "")
if _env_database_url:
    DATABASE_URL: str = _env_database_url
else:
    DB_PATH = _default_sqlite_db_path()
    DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

DEFAULT_MIN_WITHDRAW: int = env.int("DEFAULT_MIN_WITHDRAW", 20)
# Текст для админа: рекомендуемый срок «живой» проверки отзыва на площадке
REVIEW_CHECK_DAYS: int = env.int("REVIEW_CHECK_DAYS", 3)
# Через сколько минут после скрина отзыва бот пришлёт админу напоминание с кнопками Принять/Отклонить
REVIEW_REMINDER_AFTER_MINUTES: int = env.int("REVIEW_REMINDER_AFTER_MINUTES", 1)
# Как часто джоб проверяет просроченные отзывы (для REMINDER=1 поставьте 1)
REVIEW_SCHEDULER_INTERVAL_MINUTES: int = env.int("REVIEW_SCHEDULER_INTERVAL_MINUTES", 1)
SCHEDULER_INTERVAL_MINUTES: int = env.int("SCHEDULER_INTERVAL_MINUTES", 60)
