# 자연어 요청을 AI Agent(function calling 기반 요약)로 처리한다.
#
# CLAUDE.md 절대 원칙 5: LLM은 실제 판정 함수(src.graph.runner.run_full_compliance_check)가
# 반환한 값에 근거해서만 자연어 답변을 생성해야 하며, 판정 결과를 스스로 재판단하거나
# 지어내면 안 된다. handle_agent_query()는 그 함수의 반환값(호출부가 검색 시 이미 한 번
# 호출해 얻은 report — CategoryResult 리스트)을 그대로 받는다 — 여기서 판정을 다시
# 계산하는 경로는 없다.
#
# 채팅 질문마다 판정 그래프를 다시 실행하지 않는다 — 같은 건물에 대해 이미 계산된 report를
# 재사용한다. (그래프를 다시 돌리면 카테고리마다 llm_summarize_node가 또 LLM을 호출하게
# 되어, 채팅 답변 자체와 무관한 지연/실패가 늘어난다.) 그래서 이 파일은 tool로도
# tool_check_height_compliance(그래프를 재실행하는 tool)는 절대 노출하지 않고,
# tool_get_violation_citations(순수 RAG 조회, 그래프 재실행 없음)만 노출한다.
#
# 3단계 폴백: (1) CLOVASTUDIO_API_KEY가 있으면 실제 tool-calling으로 근거 조문을 정확히
# 조회해 답변 → (2) 실패하거나 키가 없으면 기존처럼 report+RAG 근거를 프롬프트에 통째로
# 채워 넣는 call_llm() 단발 호출 → (3) 그것도 실패하면 질문 키워드 기반 규칙 답변.
#
# src/agent/tools.py의 tool_check_height_compliance()는 이 판정 결과의 "공개 계약"
# (facility_type/facility_name/exceeds_limit/margin/regulation_theme/regulation_label)이다.

import logging
import time
from contextlib import nullcontext
from typing import Any, Dict, List, Optional

from src.agent.tools import tool_get_violation_citations
from src.graph.llm_client import call_llm, call_llm_with_tools
from src.graph.runner import CategoryResult
from src.graph.tracing import get_langfuse_client

logger = logging.getLogger(__name__)

_CHAT_SYSTEM_PROMPT = (
    "너는 건축 높이 컴플라이언스 판정 결과를 안내하는 상담 담당자다. 실제 민원 상담 창구처럼 "
    "정중한 존댓말로, 친절하고 명확하게 답하라. 애매하게 얼버무리지 말고, 아래 제공된 정보 "
    "안에서 확인 가능한 사실은 구체적으로 단정해서 답하라 — 예를 들어 기준 대비 여유·부족 "
    "수치가 제공된 항목이면 '기준 대비 7.00m 부족합니다. 이격거리를 최소 7m 이상 늘리시거나 "
    "계획 높이를 낮추셔야 합니다'처럼 결론과 필요한 조치까지 함께 제시하라.\n\n"
    "판정은 이미 끝났다 — 초과 여부를 스스로 재판단하지 마라. 아래 제공된 판정 결과(위반/적합), "
    "반경 검색 결과(인접 시설 현황), 기준 대비 여유·부족 수치, 근거 조문만 사용해서 사용자 "
    "질문에 답하라. '근처에 이런 시설이 있어?' 류 질문에는 아래 '반경 검색 결과'를 근거로 "
    "있다/없다를 명확히 답하라 — 모른다고 답하지 마라.\n\n"
    "'판정 결과: 위반/적합'은 군사시설을 포함한 모든 항목에서 항상 제공되는 값이다 — "
    "'몇 개 항목이 위반이야?', '제한보호구역이랑 비행안전구역 둘 다 위반이야?' 같은 질문에는 "
    "군사시설이라도 위반/적합을 그대로 답하라.\n\n"
    "군사시설의 실제 고도제한 기준값과 그 기준 대비 여유·부족 수치(margin)는 안보상 이유로 "
    "관리기관만 알 수 있고 이 서비스도 알지 못한다 — 어떤 형태로 묻든(정확한 수치, 대략적인 "
    "범위, '45m보다 큰가/작은가' 같은 예/아니오 비교, '~라고 가정하면' 같은 가정형 질문 등) "
    "절대 추측하거나 알려주지 마라. 대신 이유를 밝혀 정중히 거절하라(예: '군사시설 기준값은 "
    "안보상 비공개 정보라 알려드릴 수 없습니다'). 위반/적합 여부 자체는 비공개가 아니므로 "
    "그것까지 거절하지는 마라.\n\n"
    "지금 입력된 높이가 아닌 '다른 높이라면 어떻게 되는지' 묻는 질문(예: 45m로 지으면 "
    "괜찮은지)에는 답할 수 없다 — 이번 판정은 지금 입력된 높이 1건에 대한 결과뿐이므로, "
    "다른 높이를 확인하려면 좌측 제어반에서 그 높이로 다시 검색해야 한다고 안내하라.\n\n"
    "정확히 어떤 법령·조문을 위반했는지 묻는 질문에는 반드시 get_violation_citations 도구를 "
    "호출해 그 반환값에 있는 조문 원문만 인용하라 — 아래 컨텍스트에 요약된 근거 조문을 그대로 "
    "베끼지 말고 도구 호출로 다시 확인하라. 제공되지 않은 수치를 임의로 지어내지 마라. 위 "
    "어느 것으로도 답할 수 없는 질문이면, 단답으로 모른다고 하지 말고 어떤 정보가 없어서 "
    "답하기 어려운지 정중히 설명하라."
)

_TOOL_SPECS = [
    {
        "name": "get_violation_citations",
        "description": (
            "판정 결과 항목 하나(facility_id, regulation_theme)에 해당하는 근거 법령 조문 "
            "원문을 조회한다. '정확히 어떤 법령/조문을 위반했나' 류 질문에만 사용한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "facility_id": {"type": "string", "description": "아래 컨텍스트에 표시된 시설 ID"},
                "regulation_theme": {
                    "type": "string",
                    "description": "규정 테마 — 군사시설만 protect_zone|flight_safety, 그 외는 default",
                },
            },
            "required": ["facility_id"],
        },
    }
]

# 폴백(LLM 미사용) 모드에서 질문 의도를 대략 구분하기 위한 키워드 — 실제 자연어 이해가
# 아니라 "완전히 무관한 답을 주지 않기 위한" 최소한의 규칙 기반 분기다. LLM이 정상
# 동작하면 이 분기는 쓰이지 않는다.
_REMEDIATION_KEYWORDS = (
    "얼마나", "몇 미터", "몇미터", "몇 m", "몇m", "얼마 더", "얼마만큼", "얼마를",
    "줄여야", "낮춰야", "늘려야", "높여야", "더 필요", "얼마나 더",
)
_LAW_KEYWORDS = ("법령", "근거", "무슨 법", "어떤 법", "조문", "법적", "왜 위반", "왜 적합")
_STATUS_KEYWORDS = ("판정", "결과", "위반이야", "적합이야", "어떻게 됐", "어떻게됐", "상태")


def _execute_tool(name: str, tool_input: Dict[str, Any]) -> Any:
    """call_llm_with_tools가 호출하는 tool_executor — 실제 tool_get_violation_citations를
    그대로 호출한 결과(RAG 조문 텍스트)만 돌려준다. 판정을 재계산하는 tool은 여기 없다."""
    if name == "get_violation_citations":
        return tool_get_violation_citations(
            tool_input["facility_id"], tool_input.get("regulation_theme", "default")
        )
    raise ValueError(f"unknown tool: {name!r}")


def _display_name(item: CategoryResult) -> str:
    """같은 시설(예: 서울공항)의 규정 테마 2개(제한보호구역/비행안전구역)가 이름만으로
    구분되지 않아 생기는 혼동을 막기 위해 regulation_label을 붙인다."""
    return f"{item.facility_name} — {item.regulation_label}" if item.regulation_label else item.facility_name


def _nearby_summary_block(nearby_summary: Optional[Dict[str, Any]]) -> str:
    """반경검색 결과(src.compliance.search.summarize_nearby 반환값)를 LLM 컨텍스트 텍스트로.

    좌표/높이(Z)는 여기 없다 — exists/count/시설명·거리만 담겨 있어 그대로 노출해도
    CLAUDE.md 원칙을 위반하지 않는다(src/compliance/search.py 참고). 이 블록이 없으면
    "근처에 이런 시설 있어?" 류 질문에 LLM이 판단 근거가 없어 "모른다"로 답하게 된다.
    """
    if not nearby_summary:
        return "반경 검색 결과: (조회되지 않음)"
    if not nearby_summary.get("exists"):
        return "반경 검색 결과: 반경 내 국가유산·군사시설 없음 (일조권 사선제한은 전국 공통 적용이라 이 결과와 무관하게 항상 판정됨)"
    facility_lines = "\n".join(
        f"  - {f['facility_name']} ({f['facility_type']}, 약 {f['distance_m']}m)"
        for f in nearby_summary.get("facilities", [])
    )
    return (
        f"반경 검색 결과: 국가유산 {nearby_summary['heritage_count']}건, "
        f"군사시설 {nearby_summary['military_count']}건 존재\n{facility_lines}"
    )


def _build_grounding_context(report: List[CategoryResult], nearby_summary: Optional[Dict[str, Any]] = None) -> str:
    """반경검색 결과 + 판정 결과 + 기준 대비 수치 + (facility_id, regulation_theme) + RAG 근거
    조문 요약을 LLM 프롬프트용 텍스트로 만든다.

    plan_height/정확한 좌표는 여기 담기지 않는다. facility_id/regulation_theme은 Z값을
    담지 않는 식별자라 노출해도 무방하며, get_violation_citations 도구 호출 인자로 쓰인다.
    margin(기준 대비 여유·부족)은 군사시설에서는 항상 None이라 "비공개"로만 표시되고,
    그 외 카테고리는 이미 공개된 법령 기준에서 계산된 값이라 실제 수치를 넘긴다 — 원본
    Z값이 아니라 사용자가 직접 입력한 계획값과 공개 기준치의 차이일 뿐이므로 CLAUDE.md
    절대 원칙 1을 위반하지 않는다.
    """
    blocks = [_nearby_summary_block(nearby_summary)]
    for item in report:
        status = "위반" if item.exceeds_limit else "적합"
        if item.margin is None:
            margin_line = "기준 대비 여유·부족 수치: 비공개 (군사시설 기준값은 공개되지 않음, 위반/적합 판정 자체는 위와 같이 공개됨)"
        else:
            margin_line = f"기준 대비 여유·부족 수치: {item.margin:+.2f}m (양수=여유, 음수=부족)"
        citations = tool_get_violation_citations(item.facility_id, item.regulation_theme)
        citation_text = "\n".join(f"  - {c['text']}" for c in citations) or "  (근거 조문 없음)"
        blocks.append(
            f"[{_display_name(item)}] (facility_id={item.facility_id}, "
            f"regulation_theme={item.regulation_theme}) 판정 결과: {status}\n"
            f"{margin_line}\n근거 조문 요약(정확한 인용은 get_violation_citations 도구로 재조회):\n"
            f"{citation_text}"
        )
    return "\n\n".join(blocks)


def _remediation_fallback(report: List[CategoryResult]) -> str:
    """'얼마나 줄여야 하나' 류 질문에 대한 규칙 기반 답변 — margin이 있는 위반 항목만 다룬다."""
    lines = []
    for item in report:
        if not item.exceeds_limit:
            continue
        if item.margin is None:
            lines.append(f"- {_display_name(item)}: 위반이지만 기준값이 비공개라 부족량을 알려드릴 수 없습니다.")
        else:
            lines.append(f"- {_display_name(item)}: 기준 대비 약 {abs(item.margin):.2f}m 부족합니다.")
    if not lines:
        return "현재 위반으로 판정된 항목이 없어 조정이 필요하지 않습니다."
    return "위반 항목별 부족량은 다음과 같습니다.\n" + "\n".join(lines)


def _law_fallback(report: List[CategoryResult]) -> str:
    """'어떤 법령을 위반했나' 류 질문에 대한 규칙 기반 답변 — 카테고리별 근거 조문을 나열한다."""
    lines = []
    for item in report:
        status = "위반" if item.exceeds_limit else "적합"
        citations = tool_get_violation_citations(item.facility_id, item.regulation_theme)
        citation_text = citations[0]["text"] if citations else "(근거 조문 없음)"
        lines.append(f"- {_display_name(item)}: {status}\n  근거: {citation_text}")
    return "카테고리별 근거 법령은 다음과 같습니다.\n" + "\n".join(lines)


def _status_fallback(report: List[CategoryResult]) -> str:
    """'판정 결과 알려줘' 류 질문에 대한 규칙 기반 답변 — 위반/적합만 나열한다."""
    lines = [f"- {_display_name(item)}: {'위반' if item.exceeds_limit else '적합'}" for item in report]
    return "현재 판정 결과는 다음과 같습니다.\n" + "\n".join(lines)


def _unclear_fallback() -> str:
    """키워드로 의도를 파악하지 못했을 때 — 답을 지어내는 대신 지원 질문 유형을 안내한다."""
    return (
        "죄송합니다, 지금은 LLM이 연결되지 않아 정해진 질문 유형만 답변할 수 있습니다.\n"
        "다음과 같이 질문해보세요.\n"
        "- \"어떤 법령을 위반했나요?\" (근거 조문)\n"
        "- \"얼마나 더 필요한가요?\" (부족량)\n"
        "- \"판정 결과 알려줘\" (전체 위반/적합 현황)"
    )


def _fallback_answer(user_query: str, report: List[CategoryResult]) -> str:
    """LLM 호출이 불가능하거나 실패했을 때 쓰는 규칙 기반 답변.

    질문에 들어있는 키워드로 의도(부족량/근거법령/전체현황)를 나눠 답하고, 어느 쪽에도
    해당하지 않으면 "답할 수 없다"고 명시한다 — 아무 질문에나 같은 답을 재탕하지 않기
    위함이다. 모든 분기가 report/RAG 조회 결과만 그대로 반영하므로, LLM 장애 시에도
    판정 결과가 왜곡되어 표시되는 일은 없다 (CLAUDE.md 절대 원칙 5).
    """
    if any(keyword in user_query for keyword in _REMEDIATION_KEYWORDS):
        return _remediation_fallback(report)
    if any(keyword in user_query for keyword in _LAW_KEYWORDS):
        return _law_fallback(report)
    if any(keyword in user_query for keyword in _STATUS_KEYWORDS):
        return _status_fallback(report)
    return _unclear_fallback()


# Langfuse span에 남기는 필드 — 질문/답변 원문은 남기지 않는다(원본 텍스트는 검토되지 않은
# 자유 입력이라 이 프로젝트의 allowlist 방침상 보수적으로 제외). facility_ids/stage/latency_ms/
# question_length는 전부 Z값과 무관한 메타데이터다.
_ALLOWED_CHAT_OUTPUT_FIELDS = {"facility_ids", "stage", "latency_ms", "question_length"}


def handle_agent_query(
    user_query: str, report: List[CategoryResult], nearby_summary: Optional[Dict[str, Any]] = None
) -> str:
    """자연어 질의를 처리한다 — 3단계 폴백:

    1) CLOVASTUDIO_API_KEY가 있으면 call_llm_with_tools()로 실제 tool-calling을 시도한다.
       LLM이 필요하다고 판단하면 get_violation_citations 도구를 스스로 호출해 정확한
       조문을 조회하고, 그 반환값만 근거로 답한다 (CLAUDE.md 절대 원칙 5).
    2) 위가 불가능하거나 실패하면, report+RAG 근거를 프롬프트에 미리 채워 넣는 단발
       call_llm() 호출로 답한다 (그래프를 다시 계산하지 않는다).
    3) 그것도 실패하면 질문 키워드 기반 규칙 답변으로 대체한다.

    nearby_summary(src.compliance.search.summarize_nearby 반환값)가 있으면 "근처에 이런
    시설이 있는지" 류 질문에 답할 근거로 그라운딩 컨텍스트에 포함된다.

    Langfuse가 설정돼 있으면 이 호출 전체를 "agent_chat" span 하나로 기록한다 — 그래프
    노드(traced_node)와 달리 여기는 질문/답변 원문을 남기지 않고, facility_ids/사용된
    폴백 단계(stage)/소요시간/질문 길이만 allowlist로 남긴다 (src/graph/tracing.py 참고).
    """
    grounding_context = _build_grounding_context(report, nearby_summary)
    user_prompt = f"{grounding_context}\n\n사용자 질문: {user_query}"

    client = get_langfuse_client()
    span_input = {"facility_ids": sorted({item.facility_id for item in report}), "question_length": len(user_query)}
    span_cm = client.start_as_current_observation(name="agent_chat", input=span_input) if client else nullcontext()

    start = time.perf_counter()
    stage = "tool_calling"
    with span_cm as span:
        try:
            answer = call_llm_with_tools(_CHAT_SYSTEM_PROMPT, user_prompt, _TOOL_SPECS, _execute_tool)
        except Exception:
            logger.info("handle_agent_query: tool-calling 미사용/실패, 단발 LLM 호출로 대체", exc_info=True)
            stage = "single_call"
            try:
                answer = call_llm(_CHAT_SYSTEM_PROMPT, user_prompt)
            except Exception:
                logger.warning("handle_agent_query: LLM 호출 실패, 폴백 답변으로 대체", exc_info=True)
                stage = "rule_based"
                answer = _fallback_answer(user_query, report)

        if span is not None:
            output_fields = {
                **span_input,
                "stage": stage,
                "latency_ms": round((time.perf_counter() - start) * 1000, 2),
            }
            assert set(output_fields) <= _ALLOWED_CHAT_OUTPUT_FIELDS
            span.update(output=output_fields)

    return answer


def route_query(user_query: str) -> str:
    """사용자 자연어 질의를 "agent" 또는 "rag" 라우트로 분류"""
    # TODO: 질의 의도 분류 (판정/조회 요청 → agent, 법령/규정 질의 → rag) — 이번 작업 범위 밖
    raise NotImplementedError


def handle_rag_query(user_query: str) -> str:
    """법령 문서 기반 RAG 질의응답으로 라우팅"""
    # TODO: src.rag.qa 모듈 호출 — 이번 작업 범위 밖
    raise NotImplementedError
