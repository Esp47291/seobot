# -*- coding: utf-8 -*-
"""Время старта процесса бота (для /status и админки)."""
import time

_started_monotonic: float | None = None


def mark_started() -> None:
    global _started_monotonic
    _started_monotonic = time.monotonic()


def uptime_seconds() -> float | None:
    if _started_monotonic is None:
        return None
    return time.monotonic() - _started_monotonic
