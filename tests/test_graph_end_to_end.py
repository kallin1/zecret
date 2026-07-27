# LangGraph 컴플라이언스 파이프라인 end-to-end 검증 (Phase 2 완료 기준):
# 입력(위치+계획높이+이격거리) -> 그래프 실행 -> Phase 1 DB 기준 대비 최종 bool 결과까지
# 돌아가는지 확인한다. 세 분기(military/heritage/sunlight_setback) 모두 확인한다.

import pytest

from src.graph.build import build_compliance_graph

# config.py 샘플 좌표: 군사시설 (127.125, 37.126), 국가유산 (127.123456, 37.124123) — 서로
# 250m 이내라 군사시설이 우선 매칭된다. 국가유산 전용 경로를 타려면 군사시설 반경(1000m)
# 밖이면서 국가유산 반경 안인 좌표가 필요하다.
HERITAGE_ONLY_X, HERITAGE_ONLY_Y = 127.113456, 37.124123
FAR_FROM_ANY_X, FAR_FROM_ANY_Y = 130.0, 35.0


@pytest.fixture(scope="module")
def graph_app():
    return build_compliance_graph()


def test_military_path_violation(graph_app):
    state = graph_app.invoke(
        {"plan_x": 127.125000, "plan_y": 37.126000, "plan_height": 50.0, "setback_distance": 3.0}
    )
    assert state["facility_type"] == "military"
    assert state["computation_result"] == {"exceeds_limit": True, "margin": None}
    assert state["rag_verdict"]["exceeds_limit"] is True
    assert state["rag_verdict"]["matches_computation"] is True
    assert "height_limit_m" not in state["rag_verdict"]


def test_military_path_ok(graph_app):
    state = graph_app.invoke(
        {"plan_x": 127.125000, "plan_y": 37.126000, "plan_height": 40.0, "setback_distance": 3.0}
    )
    assert state["computation_result"] == {"exceeds_limit": False, "margin": None}
    assert state["rag_verdict"]["matches_computation"] is True


def test_heritage_path(graph_app):
    state = graph_app.invoke(
        {"plan_x": HERITAGE_ONLY_X, "plan_y": HERITAGE_ONLY_Y, "plan_height": 18.0, "setback_distance": 3.0}
    )
    assert state["facility_type"] == "heritage"
    assert state["computation_result"]["exceeds_limit"] is True
    assert state["computation_result"]["margin"] == pytest.approx(-3.0)
    assert state["rag_verdict"]["matches_computation"] is True


def test_sunlight_setback_fallback_path(graph_app):
    state = graph_app.invoke(
        {"plan_x": FAR_FROM_ANY_X, "plan_y": FAR_FROM_ANY_Y, "plan_height": 8.0, "setback_distance": 1.0}
    )
    assert state["facility_type"] == "sunlight_setback"
    assert state["computation_result"]["exceeds_limit"] is True
    assert state["rag_verdict"]["matches_computation"] is True
    assert state["final_message"] == "[인접대지경계선 (일조권 사선제한)] 판정 결과: 위반"


def test_all_paths_produce_unified_computation_schema(graph_app):
    inputs = [
        {"plan_x": 127.125000, "plan_y": 37.126000, "plan_height": 50.0, "setback_distance": 3.0},
        {"plan_x": HERITAGE_ONLY_X, "plan_y": HERITAGE_ONLY_Y, "plan_height": 10.0, "setback_distance": 3.0},
        {"plan_x": FAR_FROM_ANY_X, "plan_y": FAR_FROM_ANY_Y, "plan_height": 20.0, "setback_distance": 12.0},
    ]
    for state_input in inputs:
        state = graph_app.invoke(state_input)
        result = state["computation_result"]
        assert set(result.keys()) == {"exceeds_limit", "margin"}
        assert isinstance(result["exceeds_limit"], bool)
