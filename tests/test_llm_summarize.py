# llm_summarize_node — CLAUDE.md 절대 원칙 5(LLM 임의 응답 금지) 검증.
# LLM은 이미 확정된 computation_result만 설명하고, 판정 자체를 재판단하거나 임의의
# 수치를 지어내면 안 된다. call_llm()(CLOVA Studio 호출부)을 monkeypatch해
# 실제 API 호출 없이 검증한다.

import src.graph.nodes as nodes


def _military_state(exceeds_limit: bool):
    return {
        "facility_type": "military",
        "facility_id": "military_seongnam_airport",
        "facility_name": "성남 서울공항 비행안전구역",
        "computation_result": {"exceeds_limit": exceeds_limit, "margin": None},
    }


def _heritage_state(exceeds_limit: bool, margin: float):
    return {
        "facility_type": "heritage",
        "facility_id": "heritage_namhansanseong",
        "facility_name": "남한산성 역사문화환경보존지역",
        "computation_result": {"exceeds_limit": exceeds_limit, "margin": margin},
    }


def test_fallback_used_when_no_api_key(monkeypatch):
    monkeypatch.delenv("CLOVASTUDIO_API_KEY", raising=False)
    result = nodes.llm_summarize_node(_military_state(True))
    assert result["final_message"] == "[성남 서울공항 비행안전구역] 판정 결과: 위반"


def test_fallback_used_when_llm_call_raises(monkeypatch):
    def _boom(system_prompt, user_prompt):
        raise RuntimeError("network unreachable")

    monkeypatch.setattr(nodes, "call_llm", _boom)
    result = nodes.llm_summarize_node(_military_state(False))
    assert result["final_message"] == "[성남 서울공항 비행안전구역] 판정 결과: 적합"


def test_llm_output_used_verbatim_on_success(monkeypatch):
    monkeypatch.setattr(nodes, "call_llm", lambda system_prompt, user_prompt: "LLM이 만든 설명문입니다.")
    result = nodes.llm_summarize_node(_heritage_state(True, -3.0))
    assert result["final_message"] == "LLM이 만든 설명문입니다."


def test_llm_cannot_change_the_actual_verdict(monkeypatch):
    """LLM이 사실과 반대로 말해도(환각) computation_result 자체는 이 노드가 절대 바꾸지 않는다 —
    llm_summarize_node의 반환 dict에 computation_result 키가 아예 없어야 한다."""
    monkeypatch.setattr(
        nodes, "call_llm", lambda system_prompt, user_prompt: "사실 이 건물은 적합합니다 (거짓 진술)."
    )
    state = _military_state(True)  # 실제로는 위반
    result = nodes.llm_summarize_node(state)
    assert "computation_result" not in result
    assert state["computation_result"]["exceeds_limit"] is True  # 원본 상태는 그대로


def test_prompt_contains_anti_fabrication_instructions():
    assert "판정은 이미 끝났다" in nodes._LLM_SYSTEM_PROMPT
    assert "초과 여부를 스스로 재판단" in nodes._LLM_SYSTEM_PROMPT
    assert "근거는 아래 조문 발췌에서만 인용" in nodes._LLM_SYSTEM_PROMPT


def test_user_prompt_never_contains_raw_margin_or_coordinates():
    """프롬프트 빌더는 facility_name/exceeds_limit/citations만 받는다 — 함수 시그니처
    자체가 margin이나 plan_x/plan_y/plan_height를 받지 않으므로 구조적으로 유출 불가능하다."""
    prompt = nodes._build_user_prompt("남한산성 역사문화환경보존지역", True, [])
    assert "위반" in prompt
    assert "-3.0" not in prompt
    assert "127." not in prompt  # 좌표 형식이 프롬프트에 등장하지 않는지 확인


def test_llm_summarize_node_captures_rag_citations(monkeypatch):
    monkeypatch.delenv("CLOVASTUDIO_API_KEY", raising=False)
    result = nodes.llm_summarize_node(_heritage_state(True, -3.0))
    assert result["rag_citations"]
    assert all(c["facility_id"] == "heritage_namhansanseong" for c in result["rag_citations"])
