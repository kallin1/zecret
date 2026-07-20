# 암호문(Z)-평문(신축 건물 높이) 혼합 연산으로 기준 초과 여부만 판정 — 복호화는 이 모듈 내부에서만 수행

from dataclasses import dataclass
from typing import Any, List

from src.he.encryption import CkksContext


@dataclass
class HeightJudgment:
    """판정 결과 — 원본 Z값 필드를 포함하지 않는다 (CLAUDE.md 절대 원칙 1, 2)"""

    exceeds_threshold: bool
    grade: str  # 예: "안전" / "주의" / "위반"
    reference_token: str  # tokens.py에서 발급한 "HE:{datasetId}:{buildingIndex}" 형식


def judge_height_exceeds(
    z_enc: Any,
    new_building_height_plain: float,
    threshold_plain: float,
    ctx: CkksContext,
    dataset_id: str,
    building_index: int,
) -> HeightJudgment:
    """암호화된 기존 시설 Z값과 신축 건물 높이(평문)를 비교해 기준 초과 여부만 판정.

    내부적으로 z_enc를 복호화하여 비교하되, 반환값에는 boolean/grade/token만 담는다.
    """
    # TODO: encryption._decrypt_z_internal(z_enc, ctx) 호출 후 threshold_plain과 비교
    # TODO: tokens.issue_token(dataset_id, building_index)로 참조 토큰 발급
    raise NotImplementedError


def judge_height_exceeds_batch(
    z_enc_list: List[Any],
    new_building_height_plain: float,
    threshold_plain: float,
    ctx: CkksContext,
    dataset_id: str,
) -> List[HeightJudgment]:
    """여러 시설에 대해 배치로 기준 초과 여부 판정 (행렬/벡터 연산 활용)"""
    # TODO: 벡터화된 비교 연산 수행 후 시설별 HeightJudgment 리스트 반환
    raise NotImplementedError
