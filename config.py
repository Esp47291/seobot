# -*- coding: utf-8 -*-
"""Конфигурация бота через переменные окружения."""
import os
from typing import Optional
from datetime import datetime

from environs import Env

env = Env()
env.read_env()


def _parse_admin_ids(value: str) -> list[int]:
    if not value or not value.strip():
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()]


def _is_probably_netlify() -> bool:
    # Netlify обычно выставляет переменные NETLIFY* и при этом во время "build" часть ФС read-only.
    return bool(os.environ.get("NETLIFY") or os.environ.get("NETLIFY_BUILD_ID") or os.environ.get("NETLIFY_SITE_ID"))


def _is_ci_environment() -> bool:
    return bool(os.environ.get("CI"))


def _is_localhost_proxy(url: str) -> bool:
    value = (url or "").lower()
    return "127.0.0.1" in value or "localhost" in value


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

if (_is_probably_netlify() or _is_ci_environment()) and _is_localhost_proxy(PROXY_URL):
    # В облачных build/CI окружениях локальный прокси недоступен:
    # 127.0.0.1 относится к контейнеру сборки, а не к вашей машине.
    PROXY_URL = ""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "data", "seobot.db")


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
# Как часто проверять очередь напоминаний исполнителям (после оплаты отзыва)
EXECUTOR_REMINDER_INTERVAL_MINUTES: int = env.int("EXECUTOR_REMINDER_INTERVAL_MINUTES", 5)
# Версия для админ-команды «статус» (задайте в .env при релизе)
APP_VERSION: str = env.str("APP_VERSION", "dev")

# v2: приветственный бонус новым пользователям
WELCOME_BONUS_AMOUNT: int = env.int("WELCOME_BONUS_AMOUNT", 20)
# Дата старта начисления бонуса (МСК условно, формат YYYY-MM-DD)
WELCOME_BONUS_START_DATE: str = env.str("WELCOME_BONUS_START_DATE", "2026-05-16")

# Через сколько минут закрывать попытку, если исполнитель не отправил скрин отзыва.
TASK_EXECUTION_TIMEOUT_MINUTES: int = env.int("TASK_EXECUTION_TIMEOUT_MINUTES", 60)


def welcome_bonus_start_datetime_utc() -> datetime:
    try:
        d = datetime.strptime(WELCOME_BONUS_START_DATE.strip(), "%Y-%m-%d")
    except Exception:
        d = datetime(2026, 5, 16)
    return d
