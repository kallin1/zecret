# src/agent/router.py — handle_agent_query()의 CLAUDE.md 절대 원칙 5(LLM 임의 응답
# 금지) 검증. call_llm()을 monkeypatch해 실제 API 호출 없이 검증한다.
#
# handle_agent_query()는 이미 계산된 report(CategoryResult 리스트)를 받는다 — 채팅
# 질문마다 판정 그래프를 다시 실행하지 않는다 (tests/conftest.py의 autouse fixture가
# 매 테스트마다 CLOVASTUDIO_API_KEY를 지워주므로, 아래 report 계산은
# 항상 실제 네트워크 호출 없이 폴백 경로로 빠르게 끝난다).

import json

import pytest

import src.agent.router as router
from src.compliance.search import find_nearby_restricted_zones, summarize_nearby
from src.graph.runner import run_full_compliance_check

# 서울공항 제한보호구역(반경 5km)·남한산성 국가유산(반경 1km)이 겹치는 데모 좌표.
DEFAULT_X, DEFAULT_Y = 127.1567, 37.4504


@pytest.fixture
def default_report():
    """일조권/국가유산 위반, 군사시설 적합 — 기본 데모 위치."""
    return run_full_compliance_check(DEFAULT_X, DEFAULT_Y, 20.0, 3.0)


@pytest.fixture
def military_violation_report():
    """군사시설도 위반으로 바뀌는 높이(두 규정 테마 기준 45.0m/60.0m를 모두 초과)."""
    return run_full_compliance_check(DEFAULT_X, DEFAULT_Y, 65.0, 3.0)


@pytest.fixture
def default_nearby_summary():
    """기본 데모 좌표 기준 반경검색 결과 — 국가유산·군사시설이 모두 반경 내에 있다."""
    return summarize_nearby(find_nearby_restricted_zones(DEFAULT_X, DEFAULT_Y))


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


def test_grounding_context_includes_nearby_summary_counts(default_report, default_nearby_summary):
    """근처 시설 여부를 챗봇이 '모릅니다'로 답하지 않으려면, 반경검색 결과(개수·시설명·거리)가
    그라운딩 컨텍스트에 명시적으로 들어가야 한다."""
    context = router._build_grounding_context(default_report, default_nearby_summary)

    assert "반경 검색 결과" in context
    assert "군사시설 1건" in context
    assert "국가유산 1건" in context
    assert "서울공항" in context


def test_grounding_context_reports_no_nearby_facilities_when_absent():
    """반경 내 시설이 없는 경우에도 '모른다'가 아니라 '없다'는 사실을 명확히 답할 근거를 담는다."""
    empty_summary = {"exists": False, "heritage_count": 0, "military_count": 0, "facilities": []}
    context = router._build_grounding_context([], empty_summary)
    assert "없음" in context


def test_grounding_context_handles_missing_nearby_summary(default_report):
    """nearby_summary를 안 넘기는 기존 호출부(하위 호환)도 에러 없이 동작해야 한다."""
    context = router._build_grounding_context(default_report)
    assert "반경 검색 결과" in context


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
    assert "127.1567" not in context
    assert "37.4504" not in context


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


# --- 실제 tool-calling 경로 (요청 기능 3) ---
# conftest.py의 autouse fixture가 매 테스트 전에 CLOVASTUDIO_API_KEY를 지우므로, 이 경로를
# 검증하려면 테스트 본문에서 직접 monkeypatch.setenv()로 다시 켜야 한다.


def test_tool_calling_used_when_clovastudio_key_configured(monkeypatch, default_report):
    monkeypatch.setenv("CLOVASTUDIO_API_KEY", "nv-test-dummy")
    monkeypatch.setattr(router, "call_llm_with_tools", lambda *a, **k: "tool-calling으로 만든 답변")
    answer = router.handle_agent_query("정확히 어떤 조문을 위반했어?", default_report)
    assert answer == "tool-calling으로 만든 답변"


def test_falls_back_to_plain_call_llm_when_tool_calling_fails(monkeypatch, default_report):
    monkeypatch.setenv("CLOVASTUDIO_API_KEY", "nv-test-dummy")

    def _boom(*a, **k):
        raise RuntimeError("tool-calling unavailable")

    monkeypatch.setattr(router, "call_llm_with_tools", _boom)
    monkeypatch.setattr(router, "call_llm", lambda system_prompt, user_prompt: "단발 호출 답변")
    answer = router.handle_agent_query("설명해줘", default_report)
    assert answer == "단발 호출 답변"


def test_execute_tool_returns_real_citations_not_fabricated(default_report):
    """_execute_tool은 실제 tool_get_violation_citations를 그대로 호출한다 — LLM 없이도
    이 함수 자체가 판정 근거를 지어내지 않고 RAG 조회 결과만 반환하는지 확인한다."""
    sunlight_item = next(item for item in default_report if item.facility_type == "sunlight_setback")
    result = router._execute_tool(
        "get_violation_citations",
        {"facility_id": sunlight_item.facility_id, "regulation_theme": sunlight_item.regulation_theme},
    )
    assert any("건축법 제61조" in c["text"] for c in result)


def test_execute_tool_rejects_unknown_tool_name():
    with pytest.raises(ValueError):
        router._execute_tool("some_other_tool", {})


def test_grounding_context_includes_facility_id_for_tool_calls(default_report):
    """LLM이 get_violation_citations를 호출하려면 컨텍스트에 facility_id가 있어야 한다."""
    context = router._build_grounding_context(default_report)
    assert "facility_id=sunlight_setback_general" in context
    assert "facility_id=military_seongnam_airport" in context


# --- 챗봇 자체의 Langfuse 계측 ("langfuse에 검색 자체도 로그에 안 잡힘" 요청 대응) ---
# 그래프 노드(traced_node)와 별개로, handle_agent_query()도 "agent_chat" span 하나로
# 기록되어야 한다 — 질문/답변 원문은 남기지 않고 facility_ids/stage/latency_ms/
# question_length만 allowlist로 남긴다.


# OpenTelemetry 배치 프로세서가 flush() 이후에도 이전 테스트의 span을 뒤늦게 내보내는
# 경우가 있어(tests/test_langfuse_tracing.py와 동일한 이유), client/exporter를 세션
# 범위로 하나만 만들고 매 테스트 전에 clear()만 한다 — 테스트마다 새로 만들면 그 사이에
# 남은 span이 다음 테스트의 flush에 섞여 나올 수 있다.
@pytest.fixture(scope="session")
def _shared_chat_langfuse_exporter():
    from langfuse import Langfuse
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    client = Langfuse(
        public_key="pk-test-router", secret_key="sk-test-router", host="http://localhost:1", span_exporter=exporter
    )
    return client, exporter


@pytest.fixture
def captured_chat_spans(_shared_chat_langfuse_exporter):
    from src.graph.tracing import set_langfuse_client

    client, exporter = _shared_chat_langfuse_exporter
    exporter.clear()
    set_langfuse_client(client)
    try:
        yield client, exporter
    finally:
        set_langfuse_client(None)


def test_agent_chat_creates_langfuse_span_with_allowlisted_fields_only(
    monkeypatch, default_report, captured_chat_spans
):
    client, exporter = captured_chat_spans
    monkeypatch.setattr(
        router, "call_llm", lambda system_prompt, user_prompt: "민감한 답변 원문이 여기 들어갑니다."
    )

    def _tool_calling_unavailable(*a, **k):
        raise RuntimeError("no key configured")

    monkeypatch.setattr(router, "call_llm_with_tools", _tool_calling_unavailable)

    router.handle_agent_query("이 질문 원문은 span에 남으면 안 된다", default_report)
    client.flush()

    spans = [s for s in exporter.get_finished_spans() if s.name == "agent_chat"]
    assert len(spans) == 1
    output = json.loads(spans[0].attributes["langfuse.observation.output"])

    assert set(output.keys()) == {"facility_ids", "question_length", "stage", "latency_ms"}
    assert output["stage"] == "single_call"  # tool-calling 실패 → 단발 call_llm으로 대체됨
    assert output["question_length"] == len("이 질문 원문은 span에 남으면 안 된다")
    assert "sunlight_setback_general" in output["facility_ids"]

    blob = json.dumps({k: str(v) for k, v in spans[0].attributes.items()}, ensure_ascii=False)
    assert "이 질문 원문은 span에 남으면 안 된다" not in blob
    assert "민감한 답변 원문이 여기 들어갑니다" not in blob


def test_agent_chat_span_records_tool_calling_stage_on_success(monkeypatch, default_report, captured_chat_spans):
    client, exporter = captured_chat_spans
    monkeypatch.setattr(router, "call_llm_with_tools", lambda *a, **k: "tool-calling 답변")

    router.handle_agent_query("정확히 어떤 조문을 위반했어?", default_report)
    client.flush()

    spans = [s for s in exporter.get_finished_spans() if s.name == "agent_chat"]
    output = json.loads(spans[0].attributes["langfuse.observation.output"])
    assert output["stage"] == "tool_calling"
