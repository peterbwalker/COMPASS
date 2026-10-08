"""Great-circle geometry helpers for the MEDEVAC simulator.

All coordinates are (lat, lon) in decimal degrees. Distances in kilometres.
Threat-envelope intersection is done by sampling the great-circle path, and is
cached because the node set (facilities / bases) is small and static.
"""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Tuple

R_EARTH_KM = 6371.0088
LatLon = Tuple[float, float]


def haversine_km(a: LatLon, b: LatLon) -> float:
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dphi = lat2 - lat1
    dl = lon2 - lon1
    h = math.sin(dphi / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dl / 2) ** 2
    return 2 * R_EARTH_KM * math.asin(min(1.0, math.sqrt(h)))


def gc_interpolate(a: LatLon, b: LatLon, f: float) -> LatLon:
    """Point a fraction f (0..1) along the great circle from a to b."""
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    d = haversine_km(a, b) / R_EARTH_KM
    if d < 1e-9:
        return a
    sa = math.sin((1 - f) * d) / math.sin(d)
    sb = math.sin(f * d) / math.sin(d)
    x = sa * math.cos(lat1) * math.cos(lon1) + sb * math.cos(lat2) * math.cos(lon2)
    y = sa * math.cos(lat1) * math.sin(lon1) + sb * math.cos(lat2) * math.sin(lon2)
    z = sa * math.sin(lat1) + sb * math.sin(lat2)
    return (math.degrees(math.atan2(z, math.hypot(x, y))), math.degrees(math.atan2(y, x)))


@lru_cache(maxsize=200_000)
def path_intersects(a: LatLon, b: LatLon, center: LatLon, radius_km: float,
                    step_km: float = 20.0) -> bool:
    """True if the great-circle path a->b comes within radius_km of center."""
    length = haversine_km(a, b)
    n = max(2, int(length / step_km) + 1)
    for i in range(n + 1):
        p = gc_interpolate(a, b, i / n)
        if haversine_km(p, center) <= radius_km:
            return True
    return False
