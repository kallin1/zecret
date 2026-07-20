# AI Agent(Claude function calling)가 호출할 tool 함수 정의 — 반환값은 판정 결과(구조화 데이터)만 포함, 원본 Z값 필드 금지

from datetime import date as Date
from typing import Any, Dict, List


def tool_check_height_violation(
    x_plain: float,
    y_plain: float,
    new_building_height_plain: float,
    dataset_id: str,
) -> Dict[str, Any]:
    """[Agent tool] 지정 위치에 신축 건물을 지을 때 인근 공개제한시설 높이 기준 위반 여부 조회.

    반환값은 exceeds_threshold/grade/reference_token 등 판정 결과 필드만 포함해야 하며,
    원본 Z값(고도) 필드를 담아서는 안 된다 (CLAUDE.md 절대 원칙 1, 2).
    """
    # TODO: src.geo.range_search로 인근 시설 조회 → src.he.compare로 판정 → dict로 요약해 반환
    raise NotImplementedError


def tool_check_sunlight_violation(
    x_plain: float,
    y_plain: float,
    new_building_height_plain: float,
    target_date: Date,
    dataset_id: str,
) -> Dict[str, Any]:
    """[Agent tool] 신축 건물로 인한 일조권 침해 여부 조회 (판정 결과 요약만 반환)"""
    # TODO: src.geo.sunlight.judge_shadow_impact_batch 호출 후 결과 요약 dict 반환
    raise NotImplementedError


def tool_get_grid_risk_map(
    x_min_plain: float,
    y_min_plain: float,
    x_max_plain: float,
    y_max_plain: float,
    dataset_id: str,
) -> List[Dict[str, Any]]:
    """[Agent tool] 지정 범위의 격자 단위 위험도 목록 조회 (정밀 좌표/높이 미포함)"""
    # TODO: src.geo.grid_render.aggregate_judgments_to_grid 결과를 dict 리스트로 반환
    raise NotImplementedError


AGENT_TOOLS = [
    tool_check_height_violation,
    tool_check_sunlight_violation,
    tool_get_grid_risk_map,
]
