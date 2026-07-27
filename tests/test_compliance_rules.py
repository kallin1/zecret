# 3개 판정 카테고리(일조권 사선제한/국가유산 경관보호/군사시설 고도제한)가 각각
# 독립 함수로 분리되어 있고, evaluate_height_compliance()를 통해 동일한 반환 스키마
# {"exceeds_limit": bool, "margin": float | None}로 나오는지 확인한다.

import pytest

from src.compliance.rules import evaluate_height_compliance
from tests.he_test_helpers import encrypt_for_test


# 1) 일조권 사선제한 — 9m 이하는 1.5m 이상, 9m 초과는 높이의 1/2 이상 이격 필요


def test_setback_low_rise_requires_1_5m():
    result = evaluate_height_compliance("sunlight_setback", plan_height=8.0, reference_value=1.5)
    assert result == {"exceeds_limit": False, "margin": pytest.approx(0.0)}


def test_setback_low_rise_violation_when_under_1_5m():
    result = evaluate_height_compliance("sunlight_setback", plan_height=8.0, reference_value=1.0)
    assert result["exceeds_limit"] is True
    assert result["margin"] == pytest.approx(-0.5)


def test_setback_high_rise_requires_half_height():
    # 높이 20m -> 필요 이격거리 10m
    result = evaluate_height_compliance("sunlight_setback", plan_height=20.0, reference_value=12.0)
    assert result["exceeds_limit"] is False
    assert result["margin"] == pytest.approx(2.0)


def test_setback_high_rise_violation_when_under_half_height():
    result = evaluate_height_compliance("sunlight_setback", plan_height=20.0, reference_value=8.0)
    assert result["exceeds_limit"] is True
    assert result["margin"] == pytest.approx(-2.0)


# 2) 국가유산 경관보호 — 허용높이 초과 여부


def test_heritage_ok_when_under_allowed_height():
    result = evaluate_height_compliance("heritage", plan_height=10.0, reference_value=15.0)
    assert result == {"exceeds_limit": False, "margin": pytest.approx(5.0)}


def test_heritage_violation_when_over_allowed_height():
    result = evaluate_height_compliance("heritage", plan_height=18.0, reference_value=15.0)
    assert result["exceeds_limit"] is True
    assert result["margin"] == pytest.approx(-3.0)


# 3) 군사시설 비행안전구역 — margin은 항상 None (z값 비공개 대상, CLAUDE.md 절대 원칙 1, 2)
#
# 계획높이가 기준값과 실사용 범위(수 cm 이상)에서 떨어져 있는 케이스만 검증한다.
# plan_height가 기준값과 완전히(부동소수점 단위로) 같은 극단 케이스는 CKKS 근사
# 연산의 본질적 한계로 부호가 불안정하다 — 노이즈가 정확히 0 근처에서 양/음 어느
# 쪽으로도 튈 수 있고, 파라미터를 아무리 키워도(부트스트래핑을 붙여도) 해결되지
# 않는다. 실사용에서 사용자가 비공개인 군사시설 기준값을 정확히 알아맞혀 그 값을
# 그대로 입력할 가능성은 없으므로 이 케이스는 의도적으로 테스트에서 제외한다.


@pytest.mark.parametrize("plan_height,height_limit", [(10.0, 45.0), (44.9, 45.0), (50.0, 45.0)])
def test_military_margin_always_none(plan_height, height_limit):
    reference_value = encrypt_for_test(height_limit)
    result = evaluate_height_compliance("military", plan_height, reference_value)
    assert result["margin"] is None
    assert set(result.keys()) == {"exceeds_limit", "margin"}


def test_military_exceeds_limit_when_plan_height_over_reference():
    reference_value = encrypt_for_test(45.0)
    assert evaluate_height_compliance("military", 50.0, reference_value)["exceeds_limit"] is True
    assert evaluate_height_compliance("military", 40.0, reference_value)["exceeds_limit"] is False


# 반환 스키마 통일성 — 세 카테고리 모두 동일한 키 집합을 반환해야 한다


def test_unified_schema_keys():
    for facility_type, reference_value in [
        ("sunlight_setback", 3.0),
        ("heritage", 15.0),
        ("military", encrypt_for_test(45.0)),
    ]:
        result = evaluate_height_compliance(facility_type, plan_height=10.0, reference_value=reference_value)
        assert set(result.keys()) == {"exceeds_limit", "margin"}
        assert isinstance(result["exceeds_limit"], bool)


def test_unknown_facility_type_raises():
    with pytest.raises(ValueError):
        evaluate_height_compliance("view_right", plan_height=10.0, reference_value=1.0)
