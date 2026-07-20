# 일조량·그림자 계산 — 안심구역(평문 DEM)은 직접 계산, 공개제한구역(암호화 Z)은 he/compare.py에 위임

from datetime import date as Date
from typing import Any, List

from src.he.compare import HeightJudgment
from src.he.encryption import CkksContext


def calculate_sunlight_hours_plain(
    x_plain: float,
    y_plain: float,
    new_building_height_plain: float,
    target_date: Date,
    dem_plain: Any,
) -> float:
    """안심구역(비암호화 DEM) 대상 일조 시간(시간 단위) 계산"""
    # TODO: 태양 고도각/방위각(기상청 API 등) 기반 그림자 길이 계산 후 일조 시간 산출
    raise NotImplementedError


def judge_shadow_impact_on_restricted(
    new_building_x_plain: float,
    new_building_y_plain: float,
    new_building_height_plain: float,
    target_date: Date,
    z_enc: Any,
    ctx: CkksContext,
    dataset_id: str,
    building_index: int,
) -> HeightJudgment:
    """공개제한구역 인접 시설에 대한 일조권 침해 여부 판정 (Z는 암호문 상태로 입력, 내부에서만 복호화)"""
    # TODO: he.compare.judge_height_exceeds 등을 호출해 그림자 길이 vs 허용 기준 비교
    raise NotImplementedError


def judge_shadow_impact_batch(
    new_building_x_plain: float,
    new_building_y_plain: float,
    new_building_height_plain: float,
    target_date: Date,
    z_enc_list: List[Any],
    ctx: CkksContext,
    dataset_id: str,
) -> List[HeightJudgment]:
    """여러 공개제한시설에 대한 일조권 침해 여부 배치 판정"""
    # TODO: he.compare.judge_height_exceeds_batch 등을 호출해 벡터화 처리
    raise NotImplementedError
