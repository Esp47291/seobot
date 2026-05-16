# -*- coding: utf-8 -*-
"""Простое геокодирование городов + расчёт расстояния (для подбора ближайших заданий)."""
from __future__ import annotations

import math
from typing import Dict, Optional, Tuple

import aiohttp

_cache: Dict[str, Tuple[float, float]] = {}


def _norm_city(city: str) -> str:
    return (city or "").strip().casefold()


async def geocode_city(city: str) -> Optional[Tuple[float, float]]:
    key = _norm_city(city)
    if not key:
        return None
    if key in _cache:
        return _cache[key]

    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": city, "format": "json", "limit": "1"}
    headers = {"User-Agent": "seobot/1.0 (task-matching)"}
    try:
        timeout = aiohttp.ClientTimeout(total=6)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params, headers=headers) as resp:
                if resp.status != 200:
                    return None
                data = await resp.json()
    except Exception:
        return None

    if not data:
        return None
    try:
        lat = float(data[0]["lat"])
        lon = float(data[0]["lon"])
    except Exception:
        return None
    _cache[key] = (lat, lon)
    return (lat, lon)


def distance_km(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Расстояние между координатами по формуле гаверсинуса."""
    r = 6371.0
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))
