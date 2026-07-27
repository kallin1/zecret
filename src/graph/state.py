# LangGraph 컴플라이언스 판정 파이프라인의 공유 상태.
#
# 노드 구성(CLAUDE.md 참고): search_zone_node → (조건부 분기) → he_compute_node
# → authority_verify_node / plain_compute_node → rag_check_node → llm_summarize_node
#
# computation_result / rag_verdict는 항상 {"exceeds_limit": bool, "margin": float | None}
# 계열 스키마를 따르며, 군사시설 카테고리에서는 margin과 height_limit_m이 어떤 필드에도
# 평문으로 채워지지 않는다 (CLAUDE.md 절대 원칙 1, 2).

from typing import Any, Dict, List, Optional, TypedDict


class ComplianceState(TypedDict, total=False):
    """전체 그래프를 통과하며 누적되는 판정 상태.

    plan_x/plan_y/plan_height/setback_distance는 사용자 입력이며, facility_type/
    facility_id/facility_name은 search_zone_node가 채운다. diff_ciphertext는
    he_compute_node → authority_verify_node로만 전달되는 중간 산물이다.
    """

    # 사용자 입력
    plan_x: float
    plan_y: float
    plan_height: float
    setback_distance: float

    # search_zone_node가 채움 — facility_type: "sunlight_setback" | "heritage" | "military"
    facility_type: str
    facility_id: Optional[str]
    facility_name: Optional[str]

    # he_compute_node → authority_verify_node 전용 중간 산물 (군사시설 경로에서만 사용)
    diff_ciphertext: Optional[Any]

    # authority_verify_node 또는 plain_compute_node가 채움
    computation_result: Optional[Dict[str, Any]]

    # rag_check_node가 채움 — src/db 구조화 기준값과의 정확값 대조 결과
    rag_verdict: Optional[Dict[str, Any]]

    # llm_summarize_node가 채움 — src/rag(벡터DB)에서 조회한 근거 조문 청크(판정에는 관여하지 않음)
    rag_citations: Optional[List[Dict[str, Any]]]

    # llm_summarize_node가 채움 — 판정 결과를 설명하는 자연어 문장 (LLM이 판정 자체를 내리지 않음)
    final_message: Optional[str]
