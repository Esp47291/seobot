# -*- coding: utf-8 -*-
"""Подключение к БД и создание сессий."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from config import DATABASE_URL

# Для SQLite нужен connect_args
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    connect_args=connect_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def get_async_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def _sqlite_add_column_if_missing(conn, table: str, column: str, ddl: str) -> None:
    r = await conn.execute(text(f"PRAGMA table_info({table})"))
    cols = [row[1] for row in r.fetchall()]
    if column not in cols:
        await conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))


async def migrate_sqlite_schema() -> None:
    """Добавление колонок в существующую SQLite БД (create_all не меняет старые таблицы)."""
    if not DATABASE_URL.startswith("sqlite"):
        return
    async with engine.begin() as conn:
        await _sqlite_add_column_if_missing(conn, "task_items", "created_by_user_id", "created_by_user_id BIGINT")
        await _sqlite_add_column_if_missing(conn, "task_items", "venue_city", "venue_city VARCHAR(255) DEFAULT ''")
        await _sqlite_add_column_if_missing(conn, "attempts", "payout_requisites", "payout_requisites TEXT")
        await _sqlite_add_column_if_missing(conn, "attempts", "balance_credited", "balance_credited INTEGER NOT NULL DEFAULT 0")
        await _sqlite_add_column_if_missing(conn, "users", "payout_requisites", "payout_requisites TEXT")
        await _sqlite_add_column_if_missing(conn, "users", "task_rotation_json", "task_rotation_json TEXT DEFAULT '{}'")
        await _sqlite_add_column_if_missing(conn, "users", "repeat_unlock_json", "repeat_unlock_json TEXT DEFAULT '{}'")
        await _sqlite_add_column_if_missing(conn, "task_items", "daily_issue_count", "daily_issue_count INTEGER")
        await _sqlite_add_column_if_missing(conn, "task_items", "prebuilt_texts_json", "prebuilt_texts_json TEXT DEFAULT '[]'")
        await _sqlite_add_column_if_missing(conn, "task_items", "prebuilt_text_cursor", "prebuilt_text_cursor INTEGER NOT NULL DEFAULT 0")
        await _sqlite_add_column_if_missing(conn, "task_items", "prebuilt_texts_exhausted_notified", "prebuilt_texts_exhausted_notified INTEGER NOT NULL DEFAULT 0")
        await _sqlite_add_column_if_missing(conn, "users", "rules_accepted", "rules_accepted INTEGER NOT NULL DEFAULT 0")
        await _sqlite_add_column_if_missing(conn, "users", "rules_prompted", "rules_prompted INTEGER NOT NULL DEFAULT 0")
        await _sqlite_add_column_if_missing(conn, "users", "news_accepted", "news_accepted INTEGER NOT NULL DEFAULT 0")
        await _sqlite_add_column_if_missing(conn, "users", "news_prompted", "news_prompted INTEGER NOT NULL DEFAULT 0")


async def init_db() -> None:
    """Создание таблиц при старте."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await migrate_sqlite_schema()
