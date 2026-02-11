# -*- coding: utf-8 -*-
"""Конфигурация бота через переменные окружения."""

from environs import Env

env = Env()
env.read_env()


def _parse_admin_ids(value: str) -> list[int]:
    """Парсит список ID админов из строки (через запятую)."""
    if not value or not value.strip():
        return []
    return [int(x.strip()) for x in value.split(",") if x.strip().isdigit()]


# Токен бота
BOT_TOKEN: str = env.str("BOT_TOKEN", "")

# ID админов (через запятую в .env: ADMIN_IDS=123456789,987654321)
ADMIN_IDS: list[int] = _parse_admin_ids(env.str("ADMIN_IDS", ""))

# База данных: SQLite по умолчанию
DATABASE_URL: str = env.str(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./data/seobot.db",
)

# Лимиты (в часах)
YANDEX_COOLDOWN_HOURS: int = env.int("YANDEX_COOLDOWN_HOURS", 24)
TWOGIS_COOLDOWN_HOURS: int = env.int("TWOGIS_COOLDOWN_HOURS", 2)

# Количество шагов обучения (сообщений)
TRAINING_STEPS: int = env.int("TRAINING_STEPS", 4)
