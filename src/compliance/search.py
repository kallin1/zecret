# 반경 검색 — 계획 위치 기준으로 인접 국가유산/군사시설의 "존재 여부·개수"만 조회한다
# (요청 기능 1). 높이(Z)는 이 모듈 어디에도 등장하지 않는다 — 위치(X, Y)와 그로부터 계산된
# 거리는 CLAUDE.md 원칙 3에 따라 평문 취급 대상이라 그대로 반환해도 된다.
#
# 군사시설의 인접 반경은 시설 유형별(config.ZONE_RADIUS_BY_SUBTYPE, 군사기지법 제5조
# 지정범위 근거)로 판단하고, 국가유산은 config.ADJACENCY_RADIUS_M을 쓴다. src.graph.runner의
# 다중 테마 판정도 이 함수가 찾은 시설 목록을 그대로 재사용한다 — "어떤 시설이 인접한지"를
# 판단하는 로직을 이 모듈 하나로 모아 중복을 없앤다.

from dataclasses import dataclass
from typing import Any, Dict, List

from src.compliance import config
from src.compliance.geo_utils import haversine_m


@dataclass
class NearbyFacility:
    """반경 내에서 찾은 시설 1건 — Z값(높이)은 담지 않는다.

    x_plain/y_plain은 CLAUDE.md 원칙 3에 따라 평문 취급 대상이라 담아도 무방하다 — 다만
    지도 렌더링(app.py)에서는 이 좌표로 개별 시설 마커를 직접 그리지 않고, 격자 단위
    위험도(src.geo.risk_grid) 계산에만 내부적으로 쓴다 (CLAUDE.md 원칙 4).
    """

    facility_type: str  # "heritage" | "military"
    facility_id: str
    facility_name: str
    distance_m: float
    x_plain: float
    y_plain: float


def find_nearby_restricted_zones(plan_x_plain: float, plan_y_plain: float) -> List[NearbyFacility]:
    """계획 위치 기준 반경 내 국가유산/군사시설을 모두 찾는다."""
    found: List[NearbyFacility] = []

    for site in config.HERITAGE_SITES:
        distance_m = haversine_m(plan_x_plain, plan_y_plain, site.x_plain, site.y_plain)
        if distance_m <= config.ADJACENCY_RADIUS_M:
            found.append(
                NearbyFacility("heritage", site.facility_id, site.name, distance_m, site.x_plain, site.y_plain)
            )

    for zone in config.MILITARY_ZONES:
        distance_m = haversine_m(plan_x_plain, plan_y_plain, zone.x_plain, zone.y_plain)
        if distance_m <= config.zone_radius_m(zone):
            found.append(
                NearbyFacility("military", zone.facility_id, zone.name, distance_m, zone.x_plain, zone.y_plain)
            )

    return found


def summarize_nearby(facilities: List[NearbyFacility]) -> Dict[str, Any]:
    """존재 여부 + 유형별 개수 + 이름/거리 요약. 반환값에 Z값이 없어 그대로 UI/agent tool에
    노출해도 CLAUDE.md 절대 원칙 1·2를 위반하지 않는다."""
    return {
        "exists": bool(facilities),
        "heritage_count": sum(1 for f in facilities if f.facility_type == "heritage"),
        "military_count": sum(1 for f in facilities if f.facility_type == "military"),
        "facilities": [
            {
                "facility_type": f.facility_type,
                "facility_name": f.facility_name,
                "distance_m": round(f.distance_m, 1),
            }
            for f in facilities
        ],
    }
