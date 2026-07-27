# 두 지점 간 거리 계산 — X, Y(위치)는 평문 취급 가능 (CLAUDE.md 원칙3)

import math

_EARTH_RADIUS_M = 6_371_000.0


def haversine_m(x1: float, y1: float, x2: float, y2: float) -> float:
    """두 (경도,위도) 지점 사이의 거리(m) — Haversine 공식"""
    lat1, lat2 = math.radians(y1), math.radians(y2)
    dlat = math.radians(y2 - y1)
    dlon = math.radians(x2 - x1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))
