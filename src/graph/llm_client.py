# 공용 LLM 호출 계층 — llm_summarize_node(판정 결과 설명문)와 AI Agent 채팅
# (src/agent/router.py)이 이 모듈 하나를 공유한다.
#
# 제공자 우선순위: ANTHROPIC_API_KEY가 있으면 Claude, 없고 GEMINI_API_KEY가 있으면
# Gemini, 둘 다 없으면 RuntimeError를 낸다 — 호출부가 이 예외를 잡아 결정론적 폴백
# 문구로 대체할 책임을 진다 (CLAUDE.md 절대 원칙 5: LLM 장애가 판정 결과 자체를
# 바꾸면 안 된다).
#
# 이 모듈은 "이미 확정된 판정 결과를 설명하는 문장만 만들어라"는 시스템 프롬프트를
# 그대로 전달만 할 뿐, 여기서 판정을 재계산하거나 프롬프트 내용을 검열/가공하지 않는다
# — 프롬프트 설계(무엇을 넘길지)는 호출부(nodes.py/router.py) 책임이다.

import os


def call_llm(system_prompt: str, user_prompt: str) -> str:
    """설정된 API 키에 따라 Claude 또는 Gemini를 호출한다.

    둘 다 미설정이면 RuntimeError — 호출부에서 잡아 폴백 문구를 쓴다.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return _call_anthropic(system_prompt, user_prompt)
    if os.environ.get("GEMINI_API_KEY"):
        return _call_gemini(system_prompt, user_prompt)
    raise RuntimeError("no LLM API key configured (ANTHROPIC_API_KEY / GEMINI_API_KEY)")


def _call_anthropic(system_prompt: str, user_prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5"),
        max_tokens=400,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return response.content[0].text.strip()


def _call_gemini(system_prompt: str, user_prompt: str) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    response = client.models.generate_content(
        model=os.environ.get("GEMINI_MODEL", "gemini-2.0-flash"),
        contents=user_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            max_output_tokens=400,
            # SDK 기본 재시도는 429 응답의 retry-after(수십 초)를 그대로 기다린다 —
            # 이 앱은 자체 폴백(결정론적 답변)이 있으므로 재시도 없이 빠르게 실패해
            # 폴백으로 넘어가는 게 낫다 (파이프라인이 매 검색마다 수십 초씩 멈추는
            # 것을 방지).
            http_options=types.HttpOptions(
                timeout=15_000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        ),
    )
    return response.text.strip()
