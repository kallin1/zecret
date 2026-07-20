# 자연어 요청을 AI Agent(function calling) 또는 RAG(법령 질의응답)로 라우팅

from typing import Any, Dict


def route_query(user_query: str) -> str:
    """사용자 자연어 질의를 "agent" 또는 "rag" 라우트로 분류"""
    # TODO: 질의 의도 분류 (판정/조회 요청 → agent, 법령/규정 질의 → rag)
    raise NotImplementedError


def handle_agent_query(user_query: str) -> Dict[str, Any]:
    """Claude API function calling으로 자연어 → 파라미터 추출 → tool 호출 → 결과 요약.

    LLM은 실제 tool 함수(src/agent/tools.py)가 반환한 값에 근거해서만 자연어 요약을 생성해야 하며,
    판정 결과를 임의로 생성하면 안 된다 (CLAUDE.md 절대 원칙 5).
    """
    # TODO: anthropic SDK로 tool 정의 전달 → 함수 호출 → 반환값 기반 자연어 요약 생성
    raise NotImplementedError


def handle_rag_query(user_query: str) -> str:
    """법령 문서 기반 RAG 질의응답으로 라우팅"""
    # TODO: src.rag.qa 모듈 호출
    raise NotImplementedError
