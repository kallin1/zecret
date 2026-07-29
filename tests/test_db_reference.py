# 구조화 기준값 DB(src/db) — (facility_id, regulation_theme) 기반 정확 대조(벡터 검색 아님) 검증.
# 군사시설은 규정 테마 2건(제9조 protect_zone=45.0m / 제10조 flight_safety=60.0m)이 있다.

import pytest

from src.db.queries import verify_height_against_db


def test_military_protect_zone_below_limit_does_not_exceed():
    result = verify_height_against_db(
        "military_seongnam_airport", plan_height_plain=40.0, regulation_theme="protect_zone"
    )
    assert result["exceeds_limit"] is False


def test_military_protect_zone_above_limit_exceeds():
    result = verify_height_against_db(
        "military_seongnam_airport", plan_height_plain=50.0, regulation_theme="protect_zone"
    )
    assert result["exceeds_limit"] is True


def test_military_flight_safety_uses_its_own_threshold():
    """flight_safety 기준(60.0m)은 protect_zone(45.0m)과 달라, 50.0m는 protect_zone만 위반시킨다."""
    protect_zone = verify_height_against_db(
        "military_seongnam_airport", plan_height_plain=50.0, regulation_theme="protect_zone"
    )
    flight_safety = verify_height_against_db(
        "military_seongnam_airport", plan_height_plain=50.0, regulation_theme="flight_safety"
    )
    assert protect_zone["exceeds_limit"] is True
    assert flight_safety["exceeds_limit"] is False


def test_military_never_exposes_height_limit_m():
    """군사시설 카테고리는 어떤 plan_height/테마에도 height_limit_m을 반환값에 담지 않는다
    (CLAUDE.md 절대 원칙 1, 2)."""
    for theme in ("protect_zone", "flight_safety"):
        result = verify_height_against_db(
            "military_seongnam_airport", plan_height_plain=45.0, regulation_theme=theme
        )
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


def test_unknown_regulation_theme_raises():
    with pytest.raises(ValueError):
        verify_height_against_db(
            "military_seongnam_airport", plan_height_plain=10.0, regulation_theme="not_a_real_theme"
        )
