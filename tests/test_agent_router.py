# src/agent/router.py — handle_agent_query()의 CLAUDE.md 절대 원칙 5(LLM 임의 응답
# 금지) 검증. call_llm()을 monkeypatch해 실제 API 호출 없이 검증한다.
#
# handle_agent_query()는 이미 계산된 report(CategoryResult 리스트)를 받는다 — 채팅
# 질문마다 판정 그래프를 다시 실행하지 않는다 (tests/conftest.py의 autouse fixture가
# 매 테스트마다 ANTHROPIC_API_KEY/GEMINI_API_KEY를 지워주므로, 아래 report 계산은
# 항상 실제 네트워크 호출 없이 폴백 경로로 빠르게 끝난다).

import pytest

import src.agent.router as router
from src.graph.runner import run_full_compliance_check


@pytest.fixture
def default_report():
    """일조권/국가유산 위반, 군사시설 적합 — 기본 데모 위치."""
    return run_full_compliance_check(127.125000, 37.126000, 20.0, 3.0)


@pytest.fixture
def military_violation_report():
    """군사시설도 위반으로 바뀌는 높이."""
    return run_full_compliance_check(127.125000, 37.126000, 50.0, 3.0)


def test_fallback_used_when_no_api_key(default_report):
    answer = router.handle_agent_query("이 건물 왜 위반이야?", default_report)
    assert "위반" in answer
    assert "적합" in answer


def test_fallback_used_when_llm_call_raises(monkeypatch, default_report):
    def _boom(system_prompt, user_prompt):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(router, "call_llm", _boom)
    answer = router.handle_agent_query("판정 결과 알려줘", default_report)
    assert "위반" in answer or "적합" in answer


def test_llm_output_used_verbatim_on_success(monkeypatch, default_report):
    monkeypatch.setattr(router, "call_llm", lambda system_prompt, user_prompt: "LLM이 만든 답변입니다.")
    answer = router.handle_agent_query("설명해줘", default_report)
    assert answer == "LLM이 만든 답변입니다."


def test_grounding_context_contains_judgment_citations_and_margin_except_military(default_report):
    """LLM에 넘기는 컨텍스트에는 판정 결과(위반/적합)·근거 조문이 있어야 하고, 군사시설이
    아닌 카테고리는 기준 대비 수치도 포함해야 한다(공개된 법령 기준과 사용자 입력값의
    차이일 뿐이라 CLAUDE.md 절대 원칙 1 위반이 아니다). 군사시설은 "비공개"로만 표시되고,
    좌표·계획 높이 원본값은 어디에도 없어야 한다."""
    context = router._build_grounding_context(default_report)

    assert "위반" in context or "적합" in context
    assert "건축법 제61조" in context or "문화재보호법" in context or "군사기지" in context
    assert "-7.00m" in context  # 일조권 margin (공개 정보)
    assert "-5.00m" in context  # 국가유산 margin
    assert "비공개" in context  # 군사시설은 margin 대신 비공개 표시
    assert "127.125" not in context
    assert "37.126" not in context


def test_fallback_remediation_question_gives_shortfall_amount(default_report):
    answer = router.handle_agent_query("그럼 얼마나 줄여야해?", default_report)
    assert "부족" in answer
    assert "m" in answer


def test_fallback_law_question_gives_citations(default_report):
    answer = router.handle_agent_query("어떤 법령을 위반했어?", default_report)
    assert "건축법 제61조" in answer


def test_fallback_unclear_question_does_not_dump_unrelated_answer(default_report):
    """'엥' 같은 의도 불명 입력에는 아무 정보나 재탕하지 않고, 답할 수 없다고 명시해야 한다."""
    answer = router.handle_agent_query("엥", default_report)
    assert "건축법 제61조" not in answer
    assert "질문 유형" in answer


def test_fallback_remediation_never_reveals_military_margin(military_violation_report):
    """군사시설이 위반이어도 '얼마나 초과했는지'는 비공개로만 답해야 한다 (CLAUDE.md 절대 원칙 1, 2)."""
    answer = router.handle_agent_query("얼마나 초과했어?", military_violation_report)
    assert "비공개" in answer


def test_user_query_is_grounded_not_freely_answered(monkeypatch, default_report):
    """LLM이 뭐라고 답하든 handle_agent_query가 반환하는 값은 LLM 출력 그대로일 뿐,
    이 함수가 판정 결과를 재계산해서 끼워넣지 않는다는 것을 확인한다."""
    captured_prompts = {}

    def _capture(system_prompt, user_prompt):
        captured_prompts["system"] = system_prompt
        captured_prompts["user"] = user_prompt
        return "ok"

    monkeypatch.setattr(router, "call_llm", _capture)
    router.handle_agent_query("아무 질문", default_report)

    assert "재판단" in captured_prompts["system"]
    assert "아무 질문" in captured_prompts["user"]


def test_router_does_not_import_the_compliance_graph_entrypoint():
    """handle_agent_query가 report를 그대로 받아 쓸 뿐임을 구조적으로 확인한다 — 채팅
    질문마다 run_full_compliance_check를 다시 호출하면 카테고리별 LLM 호출까지 반복되어
    불필요하게 느려진다."""
    assert not hasattr(router, "run_full_compliance_check")
