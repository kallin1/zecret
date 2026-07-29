# AI Agent(LLM function calling)가 호출할 tool 함수 정의 — 반환값은 판정 결과(구조화 데이터)만 포함, 원본 Z값 필드 금지

from typing import Any, Dict, List

from src.compliance.search import find_nearby_restricted_zones, summarize_nearby
from src.graph.runner import run_full_compliance_check
from src.rag.qa import get_citations_for_facility


def tool_check_height_compliance(
    plan_x_plain: float,
    plan_y_plain: float,
    plan_height_plain: float,
    setback_distance_m: float,
) -> List[Dict[str, Any]]:
    """[Agent tool] 신축 예정 건물 1건이 인접 국가유산/군사시설/일조권 사선제한 기준을 위반하는지 조회.

    군사시설(보호구역/비행안전구역) 기준값은 서버 내부에서만 복호화되어 비교에 쓰이고,
    반환값에는 facility_type/facility_name/exceeds_limit/margin/regulation_theme/
    regulation_label만 담는다 — facility_id, 근거 조문, final_message 등 다른 필드는 이
    tool의 공개 계약에 포함하지 않는다. regulation_theme/regulation_label은 "어떤 규정을
    판단했는지"를 구분하기 위한 것으로 Z값을 담지 않아 노출해도 무방하다. 군사시설 항목의
    margin은 항상 None이다 (CLAUDE.md 절대 원칙 1, 2).
    """
    report = run_full_compliance_check(plan_x_plain, plan_y_plain, plan_height_plain, setback_distance_m)
    return [
        {
            "facility_type": item.facility_type,
            "facility_name": item.facility_name,
            "exceeds_limit": item.exceeds_limit,
            "margin": item.margin,
            "regulation_theme": item.regulation_theme,
            "regulation_label": item.regulation_label,
        }
        for item in report
    ]


def tool_search_nearby_restricted_zones(plan_x_plain: float, plan_y_plain: float) -> Dict[str, Any]:
    """[Agent tool] 계획 위치 기준 반경 내 국가유산/군사시설의 존재 여부·개수·거리를 조회.

    좌표(X, Y)는 CLAUDE.md 원칙 3에 따라 평문 취급 대상이라 시설명·거리까지 반환해도
    되지만, 높이(Z)는 이 tool 어디에도 등장하지 않는다. 실제 위반 여부 판정은 이 tool이
    아니라 tool_check_height_compliance가 담당한다 — 이 tool은 "무엇이 근처에 있는지"만
    답한다.
    """
    facilities = find_nearby_restricted_zones(plan_x_plain, plan_y_plain)
    return summarize_nearby(facilities)


def tool_get_violation_citations(facility_id: str, regulation_theme: str = "default") -> List[Dict[str, Any]]:
    """[Agent tool] (facility_id, regulation_theme)에 해당하는 근거 법령 조문 청크를 조회.

    RAG 벡터DB(src.rag)에서 조회한 조문 텍스트만 반환한다 — 판정을 다시 계산하지 않고,
    이미 나온 위반/적합 결과를 설명할 때 인용할 근거만 제공한다 (CLAUDE.md 절대 원칙 5).
    군사시설 조문은 고도제한 수치를 절대 포함하지 않는다.
    """
    citations = get_citations_for_facility(facility_id, regulation_theme=regulation_theme)
    return [{"text": c["text"], "effective_date": c["effective_date"]} for c in citations]


AGENT_TOOLS = [
    tool_check_height_compliance,
    tool_search_nearby_restricted_zones,
    tool_get_violation_citations,
]
