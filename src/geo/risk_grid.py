# 검색 반경을 격자(grid) 단위로 나눠 셀마다 "겹치는 인접 시설 개수"만으로 위험도를 매긴다
# (CLAUDE.md 원칙 4: 개별 건물의 정밀 좌표/높이 대신 격자 단위 위험도만 표시).
#
# 이 모듈은 시설의 위치(X, Y — 원칙 3에 따라 평문 취급 가능)와 개수만 쓰고, 높이(Z)는
# 전혀 참조하지 않는다 — src.compliance.search가 이미 찾아준 NearbyFacility 목록을
# 입력으로 받아 셀 단위로 집계할 뿐이다. app.py는 이 셀 목록만 그리고, 개별 시설의
# 정확한 위치·형태는 지도에 직접 그리지 않는다.

import math
from dataclasses import dataclass
from typing import List

from src.compliance.geo_utils import haversine_m
from src.compliance.search import NearbyFacility

_EARTH_RADIUS_M = 6_371_000.0


@dataclass
class GridCell:
    """격자 셀 1개 — 중심 좌표와 그 셀 반경 안에 걸치는 인접 시설 개수(위험도)만 담는다."""

    center_x: float
    center_y: float
    facility_count: int


def _meters_to_degrees(distance_m: float, latitude_deg: float):
    """위도 근방에서 distance_m(미터)에 대응하는 (경도, 위도) 도(degree) 폭 근사치."""
    lat_deg_per_m = 1.0 / (_EARTH_RADIUS_M * math.pi / 180.0)
    lon_deg_per_m = lat_deg_per_m / max(math.cos(math.radians(latitude_deg)), 1e-6)
    return distance_m * lon_deg_per_m, distance_m * lat_deg_per_m


def build_risk_grid(
    center_x: float,
    center_y: float,
    radius_m: float,
    facilities: List[NearbyFacility],
    cell_size_m: float = 250.0,
) -> List[GridCell]:
    """center를 중심으로 radius_m 반경을 cell_size_m 단위 격자로 나누고, 각 셀 중심에서
    cell_size_m 이내에 있는 시설 개수를 세어 위험도로 삼는다.

    반경/셀 크기가 커서 셀 수가 지나치게 많아지는 것을 막기 위해 한 변 최대 41칸(반경 기준
    ±20칸)으로 제한한다 — 시연용 지도 렌더링 성능을 위한 안전장치일 뿐, 판정 로직과는
    무관하다.
    """
    if radius_m <= 0 or cell_size_m <= 0:
        return []

    lon_step_deg, lat_step_deg = _meters_to_degrees(cell_size_m, center_y)
    steps = min(max(int(radius_m / cell_size_m), 1), 20)

    cells: List[GridCell] = []
    for i in range(-steps, steps + 1):
        for j in range(-steps, steps + 1):
            cell_x = center_x + i * lon_step_deg
            cell_y = center_y + j * lat_step_deg
            if haversine_m(center_x, center_y, cell_x, cell_y) > radius_m:
                continue
            facility_count = sum(
                1
                for f in facilities
                if haversine_m(cell_x, cell_y, f.x_plain, f.y_plain) <= cell_size_m
            )
            cells.append(GridCell(center_x=cell_x, center_y=cell_y, facility_count=facility_count))
    return cells
