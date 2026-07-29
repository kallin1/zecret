# src/agent/tools.py — AGENT_TOOLS 공개 계약 검증.
# CLAUDE.md 코딩 컨벤션: 반환값은 판정 결과(구조화 데이터)만 담아야 하며, facility_id·
# 계획 높이 원본값 등 Z값 유추가 가능한 필드는 포함하면 안 된다.

from src.agent.tools import (
    tool_check_height_compliance,
    tool_get_violation_citations,
    tool_search_nearby_restricted_zones,
)

# 서울공항 제한보호구역(반경 5km)·남한산성 국가유산(반경 1km)이 겹치는 데모 좌표.
DEFAULT_X, DEFAULT_Y = 127.1567, 37.4504


def test_returns_all_three_categories_at_default_location():
    result = tool_check_height_compliance(DEFAULT_X, DEFAULT_Y, 20.0, 3.0)
    facility_types = {item["facility_type"] for item in result}
    assert facility_types == {"sunlight_setback", "heritage", "military"}


def test_result_schema_is_exactly_six_fields():
    result = tool_check_height_compliance(DEFAULT_X, DEFAULT_Y, 20.0, 3.0)
    for item in result:
        assert set(item.keys()) == {
            "facility_type",
            "facility_name",
            "exceeds_limit",
            "margin",
            "regulation_theme",
            "regulation_label",
        }


def test_military_margin_always_none_and_has_two_themes():
    result = tool_check_height_compliance(DEFAULT_X, DEFAULT_Y, 65.0, 3.0)
    military_items = [item for item in result if item["facility_type"] == "military"]
    assert {item["regulation_theme"] for item in military_items} == {"protect_zone", "flight_safety"}
    for item in military_items:
        assert item["margin"] is None
        assert isinstance(item["exceeds_limit"], bool)
        assert item["regulation_label"]


def test_search_nearby_restricted_zones_reports_existence_and_counts():
    summary = tool_search_nearby_restricted_zones(DEFAULT_X, DEFAULT_Y)
    assert summary["exists"] is True
    assert summary["heritage_count"] == 1
    assert summary["military_count"] == 1
    assert {f["facility_type"] for f in summary["facilities"]} == {"heritage", "military"}
    for f in summary["facilities"]:
        assert "distance_m" in f and isinstance(f["distance_m"], float)


def test_search_nearby_restricted_zones_far_location_has_none():
    summary = tool_search_nearby_restricted_zones(130.0, 35.0)
    assert summary == {"exists": False, "heritage_count": 0, "military_count": 0, "facilities": []}


def test_get_violation_citations_never_mentions_numeric_height():
    citations = tool_get_violation_citations("military_seongnam_airport", "flight_safety")
    assert citations
    for c in citations:
        assert "60" not in c["text"]
        assert "45" not in c["text"]
