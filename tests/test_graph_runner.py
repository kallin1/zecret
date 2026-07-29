# src/graph/runner.py — Streamlit UI(app.py)가 실제로 소비하는 진입점 검증.
# Phase 3 완료 기준: 3개 카테고리 모두 이진 결과가 나오고, 군사시설은 margin이 항상 None이다.
#
# 데모 좌표(성남 서울공항 제한보호구역·남한산성 국가유산이 겹치는 지점): 군사시설(반경
# 5km)과 국가유산(반경 1km)이 동시에 걸리도록 config.py 좌표를 기준으로 잡은 값이다.

import pytest

from src.graph.runner import run_full_compliance_check

DEFAULT_X, DEFAULT_Y = 127.1567, 37.4504


def test_default_location_surfaces_all_three_categories():
    """서울공항 보호구역·남한산성이 겹치는 데모 좌표 기준 3개 카테고리가 모두 잡혀야 한다."""
    results = run_full_compliance_check(
        plan_x_plain=DEFAULT_X, plan_y_plain=DEFAULT_Y, plan_height_plain=20.0, setback_distance_m=3.0
    )
    facility_types = {r.facility_type for r in results}
    assert facility_types == {"sunlight_setback", "heritage", "military"}


def test_military_result_has_both_regulation_themes():
    """서울공항은 제9조(protect_zone)·제10조(flight_safety) 두 테마가 중첩 적용되므로,
    반경 안에서는 군사시설 항목이 항상 2건 나와야 한다."""
    results = run_full_compliance_check(
        plan_x_plain=DEFAULT_X, plan_y_plain=DEFAULT_Y, plan_height_plain=65.0, setback_distance_m=3.0
    )
    military_items = [r for r in results if r.facility_type == "military"]
    assert {item.regulation_theme for item in military_items} == {"protect_zone", "flight_safety"}
    for item in military_items:
        assert item.margin is None
        assert isinstance(item.exceeds_limit, bool)
        assert item.regulation_label


def test_military_themes_can_disagree():
    """계획높이가 두 테마의 기준(45.0m/60.0m) 사이에 있으면 테마별로 위반 여부가 갈려야 한다."""
    results = run_full_compliance_check(
        plan_x_plain=DEFAULT_X, plan_y_plain=DEFAULT_Y, plan_height_plain=50.0, setback_distance_m=3.0
    )
    by_theme = {item.regulation_theme: item.exceeds_limit for item in results if item.facility_type == "military"}
    assert by_theme == {"protect_zone": True, "flight_safety": False}


def test_non_military_results_carry_margin():
    results = run_full_compliance_check(
        plan_x_plain=DEFAULT_X, plan_y_plain=DEFAULT_Y, plan_height_plain=20.0, setback_distance_m=3.0
    )
    non_military_items = [r for r in results if r.facility_type != "military"]
    assert non_military_items
    for item in non_military_items:
        assert item.margin is not None


def test_far_location_only_sunlight_setback():
    results = run_full_compliance_check(
        plan_x_plain=130.0, plan_y_plain=35.0, plan_height_plain=8.0, setback_distance_m=1.0
    )
    assert len(results) == 1
    assert results[0].facility_type == "sunlight_setback"


@pytest.mark.parametrize(
    "plan_x,plan_y,plan_height,setback_distance",
    [(DEFAULT_X, DEFAULT_Y, 20.0, 3.0), (130.0, 35.0, 8.0, 1.0)],
)
def test_all_results_expose_only_bool_and_optional_margin(plan_x, plan_y, plan_height, setback_distance):
    results = run_full_compliance_check(plan_x, plan_y, plan_height, setback_distance)
    for item in results:
        assert isinstance(item.exceeds_limit, bool)
        assert item.margin is None or isinstance(item.margin, float)
