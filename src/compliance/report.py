# 판정 요청 1건(계획 건물의 위치+높이+이격거리)에 대해 3개 카테고리를 모두 실행해
# 결과 목록을 만든다. Streamlit UI(app.py)는 이 모듈만 호출하면 되고, 시설 유형별
# 노출 수준 차등화(정밀 수치 vs 이진 결과)는 UI 쪽에서 facility_type을 보고 분기한다.

from dataclasses import dataclass
from typing import List, Optional

from src.compliance import config
from src.compliance.geo_utils import haversine_m
from src.compliance.rules import evaluate_height_compliance


@dataclass
class ComplianceItem:
    """판정 결과 1건 — margin은 군사시설 카테고리에서 항상 None (CLAUDE.md 절대 원칙 1, 2)"""

    facility_type: str  # "sunlight_setback" / "heritage" / "military"
    facility_name: str
    exceeds_limit: bool
    margin: Optional[float]


def build_compliance_report(
    plan_x_plain: float,
    plan_y_plain: float,
    plan_height_plain: float,
    setback_distance_m: float,
) -> List[ComplianceItem]:
    """계획 건물 1건에 대한 전체 판정 결과 목록을 생성.

    일조권 사선제한은 항상 1건 판정하고, 국가유산/군사시설은 계획 위치로부터
    ADJACENCY_RADIUS_M 이내에 있는 것만 "인접"으로 보아 판정 대상에 포함한다.
    """
    items: List[ComplianceItem] = []

    setback_result = evaluate_height_compliance("sunlight_setback", plan_height_plain, setback_distance_m)
    items.append(
        ComplianceItem(
            facility_type="sunlight_setback",
            facility_name="인접대지경계선 (일조권 사선제한)",
            exceeds_limit=setback_result["exceeds_limit"],
            margin=setback_result["margin"],
        )
    )

    for site in config.HERITAGE_SITES:
        if haversine_m(plan_x_plain, plan_y_plain, site.x_plain, site.y_plain) > config.ADJACENCY_RADIUS_M:
            continue
        result = evaluate_height_compliance("heritage", plan_height_plain, site.allowed_height_m)
        items.append(
            ComplianceItem(
                facility_type="heritage",
                facility_name=site.name,
                exceeds_limit=result["exceeds_limit"],
                margin=result["margin"],
            )
        )

    for zone in config.MILITARY_ZONES:
        if haversine_m(plan_x_plain, plan_y_plain, zone.x_plain, zone.y_plain) > config.ADJACENCY_RADIUS_M:
            continue
        result = evaluate_height_compliance("military", plan_height_plain, zone.height_limit_enc)
        items.append(
            ComplianceItem(
                facility_type="military",
                facility_name=zone.name,
                exceeds_limit=result["exceeds_limit"],
                margin=result["margin"],
            )
        )

    return items
