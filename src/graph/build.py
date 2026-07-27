# LangGraph 그래프 조립 — 노드/조건부 분기 연결 (CLAUDE.md 그래프 오케스트레이션 절 참고).
#
#   search_zone_node --military--> he_compute_node --> authority_verify_node --+
#                     --그 외------> plain_compute_node ----------------------+--> rag_check_node --> llm_summarize_node --> END

from langgraph.graph import END, StateGraph

from src.graph.nodes import (
    authority_verify_node,
    he_compute_node,
    llm_summarize_node,
    plain_compute_node,
    rag_check_node,
    search_zone_node,
)
from src.graph.state import ComplianceState
from src.graph.tracing import traced_node


def _route_after_search(state: ComplianceState) -> str:
    return "military" if state["facility_type"] == "military" else "plain"


def build_compliance_graph():
    """컴플라이언스 판정 LangGraph를 조립하고 컴파일한 실행 가능 그래프를 반환한다.

    각 노드는 traced_node()로 감싸 Langfuse span으로 기록된다 (그래프 구조/노드 내부
    로직은 미변경 — 계측만 추가).
    """
    graph = StateGraph(ComplianceState)

    graph.add_node("search_zone", traced_node(search_zone_node, "search_zone"))
    graph.add_node("he_compute", traced_node(he_compute_node, "he_compute"))
    graph.add_node("authority_verify", traced_node(authority_verify_node, "authority_verify"))
    graph.add_node("plain_compute", traced_node(plain_compute_node, "plain_compute"))
    graph.add_node("rag_check", traced_node(rag_check_node, "rag_check"))
    graph.add_node("llm_summarize", traced_node(llm_summarize_node, "llm_summarize"))

    graph.set_entry_point("search_zone")
    graph.add_conditional_edges(
        "search_zone",
        _route_after_search,
        {"military": "he_compute", "plain": "plain_compute"},
    )
    graph.add_edge("he_compute", "authority_verify")
    graph.add_edge("authority_verify", "rag_check")
    graph.add_edge("plain_compute", "rag_check")
    graph.add_edge("rag_check", "llm_summarize")
    graph.add_edge("llm_summarize", END)

    return graph.compile()


if __name__ == "__main__":
    # 콘솔 확인용 데모 — 군사시설 경로(HE Mock) 1건 실행.
    app = build_compliance_graph()
    demo_input = {
        "plan_x": 127.125000,
        "plan_y": 37.126000,
        "plan_height": 50.0,
        "setback_distance": 3.0,
    }
    final_state = app.invoke(demo_input)
    print(final_state)
