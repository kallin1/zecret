# src/graph/runner.py — Streamlit UI(app.py)가 실제로 소비하는 진입점 검증.
# Phase 3 완료 기준: 3개 카테고리 모두 이진 결과가 나오고, 군사시설은 margin이 항상 None이다.

import pytest

from src.graph.runner import run_full_compliance_check


def test_default_location_surfaces_all_three_categories():
    """app.py 사이드바 기본값(경도 127.125/위도 37.126) 기준 3개 카테고리가 모두 잡혀야 한다."""
    results = run_full_compliance_check(
        plan_x_plain=127.125000, plan_y_plain=37.126000, plan_height_plain=20.0, setback_distance_m=3.0
    )
    facility_types = {r.facility_type for r in results}
    assert facility_types == {"sunlight_setback", "heritage", "military"}


def test_military_result_margin_always_none():
    results = run_full_compliance_check(
        plan_x_plain=127.125000, plan_y_plain=37.126000, plan_height_plain=50.0, setback_distance_m=3.0
    )
    military_items = [r for r in results if r.facility_type == "military"]
    assert military_items
    for item in military_items:
        assert item.margin is None
        assert isinstance(item.exceeds_limit, bool)


def test_non_military_results_carry_margin():
    results = run_full_compliance_check(
        plan_x_plain=127.125000, plan_y_plain=37.126000, plan_height_plain=20.0, setback_distance_m=3.0
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
    [(127.125000, 37.126000, 20.0, 3.0), (130.0, 35.0, 8.0, 1.0)],
)
def test_all_results_expose_only_bool_and_optional_margin(plan_x, plan_y, plan_height, setback_distance):
    results = run_full_compliance_check(plan_x, plan_y, plan_height, setback_distance)
    for item in results:
        assert isinstance(item.exceeds_limit, bool)
        assert item.margin is None or isinstance(item.margin, float)
