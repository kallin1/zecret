# AI Agent(LLM function calling)가 호출할 tool 함수 정의 — 반환값은 판정 결과(구조화 데이터)만 포함, 원본 Z값 필드 금지

from typing import Any, Dict, List

from src.graph.runner import run_full_compliance_check


def tool_check_height_compliance(
    plan_x_plain: float,
    plan_y_plain: float,
    plan_height_plain: float,
    setback_distance_m: float,
) -> List[Dict[str, Any]]:
    """[Agent tool] 신축 예정 건물 1건이 인접 국가유산/군사시설/일조권 사선제한 기준을 위반하는지 조회.

    군사시설(비행안전구역) 기준값은 서버 내부에서만 복호화되어 비교에 쓰이고, 반환값에는
    facility_type/facility_name/exceeds_limit/margin만 담는다 — facility_id, 근거 조문,
    final_message 등 다른 필드는 이 tool의 공개 계약에 포함하지 않는다. 군사시설 항목의
    margin은 항상 None이다 (CLAUDE.md 절대 원칙 1, 2).
    """
    report = run_full_compliance_check(plan_x_plain, plan_y_plain, plan_height_plain, setback_distance_m)
    return [
        {
            "facility_type": item.facility_type,
            "facility_name": item.facility_name,
            "exceeds_limit": item.exceeds_limit,
            "margin": item.margin,
        }
        for item in report
    ]


AGENT_TOOLS = [
    tool_check_height_compliance,
]
