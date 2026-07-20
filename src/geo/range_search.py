# BBOX/반경 기반 범위검색 — 위치(X, Y)는 평문으로 취급 가능 (체크포인트②)

from dataclasses import dataclass
from typing import List


@dataclass
class FacilityLocation:
    """범위검색 결과로 노출 가능한 위치 정보 — Z(높이)는 포함하지 않는다"""

    dataset_id: str
    building_index: int
    x_plain: float
    y_plain: float


def search_by_bbox(
    x_min_plain: float,
    y_min_plain: float,
    x_max_plain: float,
    y_max_plain: float,
    dataset_id: str,
) -> List[FacilityLocation]:
    """사각형 범위(BBOX) 내 공개제한시설 위치 목록 검색 (X, Y만 평문 반환)"""
    # TODO: data/restricted_facilities.csv 또는 DB에서 X,Y 기준으로 범위 내 항목 조회
    raise NotImplementedError


def search_by_radius(
    center_x_plain: float,
    center_y_plain: float,
    radius_m: float,
    dataset_id: str,
) -> List[FacilityLocation]:
    """중심점 기준 반경 내 공개제한시설 위치 목록 검색 (X, Y만 평문 반환)"""
    # TODO: 반경 계산(Haversine 등) 후 범위 내 항목 조회
    raise NotImplementedError
