# src/agent/tools.py — tool_check_height_compliance()의 공개 계약 검증.
# CLAUDE.md 코딩 컨벤션: 반환값은 facility_type/facility_name/exceeds_limit/margin만
# 담아야 하며, facility_id·근거 조문·계획 높이 원본값 등은 포함하면 안 된다.

from src.agent.tools import tool_check_height_compliance


def test_returns_all_three_categories_at_default_location():
    result = tool_check_height_compliance(127.125000, 37.126000, 20.0, 3.0)
    facility_types = {item["facility_type"] for item in result}
    assert facility_types == {"sunlight_setback", "heritage", "military"}


def test_result_schema_is_exactly_four_fields():
    result = tool_check_height_compliance(127.125000, 37.126000, 20.0, 3.0)
    for item in result:
        assert set(item.keys()) == {"facility_type", "facility_name", "exceeds_limit", "margin"}


def test_military_margin_always_none():
    result = tool_check_height_compliance(127.125000, 37.126000, 50.0, 3.0)
    military_items = [item for item in result if item["facility_type"] == "military"]
    assert military_items
    for item in military_items:
        assert item["margin"] is None
        assert isinstance(item["exceeds_limit"], bool)
