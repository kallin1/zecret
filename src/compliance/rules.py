# 높이 컴플라이언스 3개 판정 카테고리 — 일조권 사선제한 / 국가유산 경관보호 / 군사시설 고도제한.
# 세 함수 모두 evaluate_height_compliance()를 통해 동일한 반환 스키마
# {"exceeds_limit": bool, "margin": float | None}로 나온다.
#
# margin은 1)일조권, 2)국가유산 카테고리에서는 실제 초과/여유량을 채우고,
# 3)군사시설 카테고리에서는 항상 None이다 — 이 카테고리만 z값(높이) 비공개 대상이라
# 정밀 수치를 반환값에 담지 않기 때문 (CLAUDE.md 절대 원칙 1, 2).

from typing import Any, Dict

from scripts.mock_authority_verify import verify_diff
from src.compliance.config import (
    SUNLIGHT_SETBACK_HEIGHT_THRESHOLD_M,
    SUNLIGHT_SETBACK_LOW_RISE_MIN_DISTANCE_M,
)
from src.he.encryption import HeightLimitCiphertext, compute_diff_ciphertext


def _evaluate_sunlight_setback(plan_height: float, setback_distance_m: float) -> Dict[str, Any]:
    """일조권 사선제한 (건축법 제61조, 시행령 제86조).

    높이 9m 이하는 인접대지경계선으로부터 1.5m 이상, 9m 초과는 해당 높이의 1/2 이상
    이격해야 한다. margin은 (실제 이격거리 - 요구 이격거리)로, 음수면 위반이다.
    """
    required_distance_m = (
        SUNLIGHT_SETBACK_LOW_RISE_MIN_DISTANCE_M
        if plan_height <= SUNLIGHT_SETBACK_HEIGHT_THRESHOLD_M
        else plan_height / 2.0
    )
    margin = setback_distance_m - required_distance_m
    return {"exceeds_limit": margin < 0, "margin": margin}


def _evaluate_heritage(plan_height: float, allowed_height_m: float) -> Dict[str, Any]:
    """국가유산 경관보호 (문화재보호법, 유산별 개별 고시 허용높이).

    margin은 (허용높이 - 계획높이)로, 음수면 허용높이 초과(위반)다.
    """
    margin = allowed_height_m - plan_height
    return {"exceeds_limit": margin < 0, "margin": margin}


def _evaluate_military(plan_height: float, reference_value: HeightLimitCiphertext) -> Dict[str, Any]:
    """군사시설 비행안전구역 고도제한 (군사기지 및 군사시설 보호법).

    reference_value(높이제한 기준값 암호문)는 이 함수 안에서도 복호화하지 않는다 —
    공개 컨텍스트로 동형 뺄셈만 수행하고, 부호(초과 여부) 확인은
    scripts.mock_authority_verify.verify_diff()(관리기관 HSM 자리)로 위임한다.
    margin은 항상 None으로 반환한다 — 이 카테고리만 z값 비공개 대상이기 때문이다
    (CLAUDE.md 절대 원칙 1, 2).
    """
    diff = compute_diff_ciphertext(reference_value, plan_height)
    exceeds = verify_diff(diff.diff_enc)
    return {"exceeds_limit": exceeds, "margin": None}


def evaluate_height_compliance(facility_type: str, plan_height: float, reference_value: Any) -> Dict[str, Any]:
    """3개 판정 카테고리 공통 진입점.

    facility_type: "sunlight_setback" | "heritage" | "military"
    reference_value: sunlight_setback이면 이격거리(m), heritage면 허용높이(m),
                      military면 HeightLimitCiphertext(실제 CKKS 암호문).

    반환 스키마는 항상 {"exceeds_limit": bool, "margin": float | None}로 고정된다
    (군사시설 카테고리로 교체되어도 호출부가 바뀌지 않도록 하기 위함).
    """
    if facility_type == "sunlight_setback":
        return _evaluate_sunlight_setback(plan_height, reference_value)
    if facility_type == "heritage":
        return _evaluate_heritage(plan_height, reference_value)
    if facility_type == "military":
        return _evaluate_military(plan_height, reference_value)
    raise ValueError(f"unknown facility_type: {facility_type!r}")
