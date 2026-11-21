"""Cálculos aproximados de proximidad geográfica y temporal."""
from __future__ import annotations

import math
from datetime import datetime

EARTH_RADIUS_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def distance_or_none(lat1, lon1, lat2, lon2) -> float | None:
    if None in (lat1, lon1, lat2, lon2):
        return None
    return round(haversine_km(lat1, lon1, lat2, lon2), 3)


def hours_between(a: datetime | None, b: datetime | None) -> float | None:
    if a is None or b is None:
        return None
    return round(abs((a - b).total_seconds()) / 3600, 2)


def valid_coords(lat: float | None, lon: float | None) -> bool:
    if lat is None and lon is None:
        return True
    if lat is None or lon is None:
        return False
    return -90 <= lat <= 90 and -180 <= lon <= 180
