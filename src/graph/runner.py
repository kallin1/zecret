# Streamlit UI(app.py)가 LangGraph 판정 파이프라인 실행 결과를 받아 렌더링할 수 있도록
# 감싸는 러너. search_zone_node는 "우선순위가 가장 높은 시설 1건"만 고르도록 설계되어
# 있어(military 최우선) 화면에 3개 카테고리를 모두 보여주는 용도에는 맞지 않으므로, 이
# 모듈은 카테고리별로 그래프를 직접 실행한다.
#
# he_compute_node/authority_verify_node/plain_compute_node/rag_check_node/
# llm_summarize_node(Phase 2에서 구현된 노드)는 그대로 재사용하며, 노드 내부 로직은
# 전혀 건드리지 않는다 — "어떤 시설에 대해 그래프를 실행할지"를 정하는 열거(enumeration)
# 만 이 모듈이 새로 담당한다 (search_zone_node와 동일한 반경 규칙, CLAUDE.md 체크포인트 ②).

from dataclasses import dataclass
from typing import List, Optional

from langgraph.graph import END, StateGraph

from src.compliance import config
from src.compliance.geo_utils import haversine_m
from src.graph.nodes import (
    SUNLIGHT_SETBACK_FACILITY_ID,
    SUNLIGHT_SETBACK_FACILITY_NAME,
    authority_verify_node,
    he_compute_node,
    llm_summarize_node,
    plain_compute_node,
    rag_check_node,
)
from src.graph.state import ComplianceState
from src.graph.tracing import traced_node


def _build_military_subgraph():
    """search_zone_node 없이 military 경로만 실행하는 서브그래프 (노드 함수는 미변경).

    각 노드는 traced_node()로 감싸 Langfuse span으로 기록된다.
    """
    graph = StateGraph(ComplianceState)
    graph.add_node("he_compute", traced_node(he_compute_node, "he_compute"))
    graph.add_node("authority_verify", traced_node(authority_verify_node, "authority_verify"))
    graph.add_node("rag_check", traced_node(rag_check_node, "rag_check"))
    graph.add_node("llm_summarize", traced_node(llm_summarize_node, "llm_summarize"))
    graph.set_entry_point("he_compute")
    graph.add_edge("he_compute", "authority_verify")
    graph.add_edge("authority_verify", "rag_check")
    graph.add_edge("rag_check", "llm_summarize")
    graph.add_edge("llm_summarize", END)
    return graph.compile()


def _build_plain_subgraph():
    """search_zone_node 없이 평문 연산(sunlight_setback/heritage) 경로만 실행하는 서브그래프.

    각 노드는 traced_node()로 감싸 Langfuse span으로 기록된다.
    """
    graph = StateGraph(ComplianceState)
    graph.add_node("plain_compute", traced_node(plain_compute_node, "plain_compute"))
    graph.add_node("rag_check", traced_node(rag_check_node, "rag_check"))
    graph.add_node("llm_summarize", traced_node(llm_summarize_node, "llm_summarize"))
    graph.set_entry_point("plain_compute")
    graph.add_edge("plain_compute", "rag_check")
    graph.add_edge("rag_check", "llm_summarize")
    graph.add_edge("llm_summarize", END)
    return graph.compile()


_MILITARY_SUBGRAPH = _build_military_subgraph()
_PLAIN_SUBGRAPH = _build_plain_subgraph()


@dataclass
class CategoryResult:
    """화면 렌더링용 판정 결과 1건.

    margin은 데이터 계층(그래프의 computation_result)에는 존재하지만, 이 필드를 읽는
    쪽(app.py)은 exceeds_limit만 렌더링해야 한다 (CLAUDE.md 절대 원칙 1, 2 / 체크포인트 ③).

    regulation_theme/regulation_label은 "어떤 규정에서 위반했는지" 구분하는 필드다 — 군사
    시설처럼 규정 테마가 여러 개인 시설은 항목이 테마 수만큼 나뉘어 반환된다.
    """

    facility_type: str
    facility_id: str
    facility_name: str
    exceeds_limit: bool
    margin: Optional[float]
    final_message: str
    regulation_theme: str = "default"
    regulation_label: str = ""


def _to_category_result(state: ComplianceState) -> CategoryResult:
    result = state["computation_result"]
    return CategoryResult(
        facility_type=state["facility_type"],
        facility_id=state["facility_id"],
        facility_name=state["facility_name"],
        exceeds_limit=result["exceeds_limit"],
        margin=result["margin"],
        final_message=state["final_message"],
        regulation_theme=state.get("regulation_theme") or "default",
        regulation_label=state.get("regulation_label") or "",
    )


def run_full_compliance_check(
    plan_x_plain: float,
    plan_y_plain: float,
    plan_height_plain: float,
    setback_distance_m: float,
) -> List[CategoryResult]:
    """계획 건물 1건에 대해 일조권/국가유산/군사시설 전부를 LangGraph 파이프라인으로 판정한다.

    일조권 사선제한은 항상 판정하고, 국가유산은 config.ADJACENCY_RADIUS_M, 군사시설은
    시설 유형별 반경(config.zone_radius_m, 군사기지법 제5조 지정범위 근거) 이내에 있는
    것만 인접 판정 대상에 포함한다. 군사시설은 규정 테마(예: 제9조 보호구역/제10조 비행
    안전구역)마다 독립적으로 판정해, 같은 시설이라도 테마별로 위반/적합이 갈릴 수 있다.
    """
    results: List[CategoryResult] = []

    setback_state = _PLAIN_SUBGRAPH.invoke(
        {
            "facility_type": "sunlight_setback",
            "facility_id": SUNLIGHT_SETBACK_FACILITY_ID,
            "facility_name": SUNLIGHT_SETBACK_FACILITY_NAME,
            "plan_height": plan_height_plain,
            "setback_distance": setback_distance_m,
            "regulation_theme": "default",
            "regulation_label": "",
        }
    )
    results.append(_to_category_result(setback_state))

    for site in config.HERITAGE_SITES:
        if haversine_m(plan_x_plain, plan_y_plain, site.x_plain, site.y_plain) > config.ADJACENCY_RADIUS_M:
            continue
        heritage_state = _PLAIN_SUBGRAPH.invoke(
            {
                "facility_type": "heritage",
                "facility_id": site.facility_id,
                "facility_name": site.name,
                "plan_height": plan_height_plain,
                "setback_distance": setback_distance_m,
                "regulation_theme": "default",
                "regulation_label": "",
            }
        )
        results.append(_to_category_result(heritage_state))

    for zone in config.MILITARY_ZONES:
        if haversine_m(plan_x_plain, plan_y_plain, zone.x_plain, zone.y_plain) > config.zone_radius_m(zone):
            continue
        for regulation in zone.regulations:
            military_state = _MILITARY_SUBGRAPH.invoke(
                {
                    "facility_type": "military",
                    "facility_id": zone.facility_id,
                    "facility_name": zone.name,
                    "plan_height": plan_height_plain,
                    "setback_distance": setback_distance_m,
                    "regulation_theme": regulation.theme_id,
                    "regulation_label": regulation.label,
                }
            )
            results.append(_to_category_result(military_state))

    return results
