# 자연어 요청을 AI Agent(function calling 기반 요약)로 처리한다.
#
# CLAUDE.md 절대 원칙 5: LLM은 실제 판정 함수(src.graph.runner.run_full_compliance_check)가
# 반환한 값에 근거해서만 자연어 답변을 생성해야 하며, 판정 결과를 스스로 재판단하거나
# 지어내면 안 된다. handle_agent_query()는 그 함수의 반환값(호출부가 검색 시 이미 한 번
# 호출해 얻은 report — CategoryResult 리스트)과 RAG 근거 조문을 프롬프트에 그대로 채워
# 넣고 "이미 나온 결과를 설명하라"는 지침만 LLM에 준다 — LLM이 판정 자체를 다시 계산하는
# 경로는 없다.
#
# 채팅 질문마다 판정 그래프를 다시 실행하지 않는다 — 같은 건물에 대해 이미 계산된 report를
# 재사용한다. (그래프를 다시 돌리면 카테고리마다 llm_summarize_node가 또 LLM을 호출하게
# 되어, 채팅 답변 자체와 무관한 지연/실패가 늘어난다.)
#
# src/agent/tools.py의 tool_check_height_compliance()는 이 판정 결과의 "공개 계약"
# (facility_type/facility_name/exceeds_limit/margin)이다.

import logging
from typing import List

from src.graph.llm_client import call_llm
from src.graph.runner import CategoryResult
from src.rag.qa import get_citations_for_facility

logger = logging.getLogger(__name__)

_CHAT_SYSTEM_PROMPT = (
    "너는 건축 높이 컴플라이언스 판정 결과를 설명하는 어시스턴트다. "
    "판정은 이미 끝났다 — 초과 여부를 스스로 재판단하지 마라. 아래 제공된 판정 결과"
    "(위반/적합), 기준 대비 여유·부족 수치, 근거 조문만 사용해서 사용자 질문에 답하라. "
    "군사시설 항목은 기준 대비 수치가 항상 비공개로 표시된다 — 이 경우 구체적인 "
    "초과/부족량을 추측하거나 지어내지 말고 비공개라고 답하라. 그 외 항목은 제공된 "
    "수치를 근거로 '몇 미터 더 필요한지' 같은 질문에 답해도 된다. 제공되지 않은 수치를 "
    "임의로 지어내지 마라. 근거는 제공된 조문 발췌에서만 인용하라. 제공된 정보로 답할 "
    "수 없는 질문이면 모른다고 답하라."
)

# 폴백(LLM 미사용) 모드에서 질문 의도를 대략 구분하기 위한 키워드 — 실제 자연어 이해가
# 아니라 "완전히 무관한 답을 주지 않기 위한" 최소한의 규칙 기반 분기다. LLM이 정상
# 동작하면 이 분기는 쓰이지 않는다.
_REMEDIATION_KEYWORDS = (
    "얼마나", "몇 미터", "몇미터", "몇 m", "몇m", "얼마 더", "얼마만큼", "얼마를",
    "줄여야", "낮춰야", "늘려야", "높여야", "더 필요", "얼마나 더",
)
_LAW_KEYWORDS = ("법령", "근거", "무슨 법", "어떤 법", "조문", "법적", "왜 위반", "왜 적합")
_STATUS_KEYWORDS = ("판정", "결과", "위반이야", "적합이야", "어떻게 됐", "어떻게됐", "상태")


def _build_grounding_context(report: List[CategoryResult]) -> str:
    """판정 결과 + 기준 대비 수치 + RAG 근거 조문을 LLM 프롬프트용 텍스트로 만든다.

    facility_id/plan_height/정확한 좌표는 여기 담기지 않는다. margin(기준 대비 여유·
    부족)은 군사시설에서는 항상 None이라 "비공개"로만 표시되고, 그 외 카테고리는 이미
    공개된 법령 기준에서 계산된 값이라 실제 수치를 넘긴다 — 원본 Z값이 아니라 사용자가
    직접 입력한 계획값과 공개 기준치의 차이일 뿐이므로 CLAUDE.md 절대 원칙 1을 위반하지
    않는다.
    """
    blocks = []
    for item in report:
        status = "위반" if item.exceeds_limit else "적합"
        if item.margin is None:
            margin_line = "기준 대비 여유·부족 수치: 비공개 (군사시설 기준값은 공개되지 않음)"
        else:
            margin_line = f"기준 대비 여유·부족 수치: {item.margin:+.2f}m (양수=여유, 음수=부족)"
        citations = get_citations_for_facility(item.facility_id)
        citation_text = "\n".join(f"  - {c['text']}" for c in citations) or "  (근거 조문 없음)"
        blocks.append(
            f"[{item.facility_name}] 판정 결과: {status}\n{margin_line}\n근거 조문:\n{citation_text}"
        )
    return "\n\n".join(blocks)


def _remediation_fallback(report: List[CategoryResult]) -> str:
    """'얼마나 줄여야 하나' 류 질문에 대한 규칙 기반 답변 — margin이 있는 위반 항목만 다룬다."""
    lines = []
    for item in report:
        if not item.exceeds_limit:
            continue
        if item.margin is None:
            lines.append(f"- {item.facility_name}: 위반이지만 기준값이 비공개라 부족량을 알려드릴 수 없습니다.")
        else:
            lines.append(f"- {item.facility_name}: 기준 대비 약 {abs(item.margin):.2f}m 부족합니다.")
    if not lines:
        return "현재 위반으로 판정된 항목이 없어 조정이 필요하지 않습니다."
    return "위반 항목별 부족량은 다음과 같습니다.\n" + "\n".join(lines)


def _law_fallback(report: List[CategoryResult]) -> str:
    """'어떤 법령을 위반했나' 류 질문에 대한 규칙 기반 답변 — 카테고리별 근거 조문을 나열한다."""
    lines = []
    for item in report:
        status = "위반" if item.exceeds_limit else "적합"
        citations = get_citations_for_facility(item.facility_id)
        citation_text = citations[0]["text"] if citations else "(근거 조문 없음)"
        lines.append(f"- {item.facility_name}: {status}\n  근거: {citation_text}")
    return "카테고리별 근거 법령은 다음과 같습니다.\n" + "\n".join(lines)


def _status_fallback(report: List[CategoryResult]) -> str:
    """'판정 결과 알려줘' 류 질문에 대한 규칙 기반 답변 — 위반/적합만 나열한다."""
    lines = [f"- {item.facility_name}: {'위반' if item.exceeds_limit else '적합'}" for item in report]
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


def handle_agent_query(user_query: str, report: List[CategoryResult]) -> str:
    """자연어 질의를 처리한다: 이미 계산된 판정 결과(report)+RAG 근거를 컨텍스트로
    LLM에 전달 → 자연어 답변 생성.

    report는 호출부(app.py)가 검색 시 이미 run_full_compliance_check()를 호출해서 얻은
    결과를 그대로 넘겨받는다 — 여기서 판정을 다시 계산하지 않는다 (CLAUDE.md 절대 원칙 5).
    call_llm()이 Claude/Gemini 중 설정된 쪽을 자동으로 고르고, 호출이 실패하면 질문
    키워드에 맞는 규칙 기반 폴백 답변으로 대체한다.
    """
    grounding_context = _build_grounding_context(report)
    user_prompt = f"{grounding_context}\n\n사용자 질문: {user_query}"

    try:
        return call_llm(_CHAT_SYSTEM_PROMPT, user_prompt)
    except Exception:
        logger.warning("handle_agent_query: LLM 호출 실패, 폴백 답변으로 대체", exc_info=True)
        return _fallback_answer(user_query, report)


def route_query(user_query: str) -> str:
    """사용자 자연어 질의를 "agent" 또는 "rag" 라우트로 분류"""
    # TODO: 질의 의도 분류 (판정/조회 요청 → agent, 법령/규정 질의 → rag) — 이번 작업 범위 밖
    raise NotImplementedError


def handle_rag_query(user_query: str) -> str:
    """법령 문서 기반 RAG 질의응답으로 라우팅"""
    # TODO: src.rag.qa 모듈 호출 — 이번 작업 범위 밖
    raise NotImplementedError
