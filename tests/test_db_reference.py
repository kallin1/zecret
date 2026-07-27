# 구조화 기준값 DB(src/db) — facility_id 기반 정확 대조(벡터 검색 아님) 검증.
# Phase 1 완료 기준: 임의 계획높이를 넣으면 DB 기준과 대조해서 bool이 정확히 반환된다.

import pytest

from src.db.queries import verify_height_against_db


def test_military_below_limit_does_not_exceed():
    result = verify_height_against_db("military_seongnam_airport", plan_height_plain=40.0)
    assert result["exceeds_limit"] is False


def test_military_above_limit_exceeds():
    result = verify_height_against_db("military_seongnam_airport", plan_height_plain=50.0)
    assert result["exceeds_limit"] is True


def test_military_never_exposes_height_limit_m():
    """군사시설 카테고리는 어떤 plan_height에도 height_limit_m을 반환값에 담지 않는다
    (CLAUDE.md 절대 원칙 1, 2)."""
    result = verify_height_against_db("military_seongnam_airport", plan_height_plain=45.0)
    assert "height_limit_m" not in result


def test_heritage_below_limit_does_not_exceed():
    result = verify_height_against_db("heritage_namhansanseong", plan_height_plain=10.0)
    assert result["exceeds_limit"] is False
    assert result["height_limit_m"] == pytest.approx(15.0)


def test_heritage_above_limit_exceeds():
    result = verify_height_against_db("heritage_namhansanseong", plan_height_plain=18.0)
    assert result["exceeds_limit"] is True


@pytest.mark.parametrize(
    "plan_height,setback_distance,expected_exceeds",
    [
        (8.0, 1.5, False),  # 9m 이하 -> 1.5m 이상 필요, 충족
        (8.0, 1.0, True),  # 9m 이하 -> 1.5m 미달, 위반
        (20.0, 10.0, False),  # 9m 초과 -> 높이의 절반(10m) 이상 필요, 충족
        (20.0, 8.0, True),  # 9m 초과 -> 10m 미달, 위반
    ],
)
def test_sunlight_setback_matches_formula(plan_height, setback_distance, expected_exceeds):
    result = verify_height_against_db(
        "sunlight_setback_general", plan_height_plain=plan_height, setback_distance_m=setback_distance
    )
    assert result["exceeds_limit"] is expected_exceeds


def test_unknown_facility_id_raises():
    with pytest.raises(ValueError):
        verify_height_against_db("does_not_exist", plan_height_plain=10.0)
