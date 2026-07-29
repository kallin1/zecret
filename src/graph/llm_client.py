# 공용 LLM 호출 계층 — llm_summarize_node(판정 결과 설명문)와 AI Agent 채팅
# (src/agent/router.py)이 이 모듈 하나를 공유한다.
#
# 제공자: 네이버클라우드 CLOVA Studio(HyperCLOVA X) 단일 제공자. CLOVASTUDIO_API_KEY가
# 없으면 RuntimeError를 낸다 — 호출부가 이 예외를 잡아 결정론적 폴백 문구로 대체할
# 책임을 진다 (CLAUDE.md 절대 원칙 5: LLM 장애가 판정 결과 자체를 바꾸면 안 된다).
#
# 이 모듈은 "이미 확정된 판정 결과를 설명하는 문장만 만들어라"는 시스템 프롬프트를
# 그대로 전달만 할 뿐, 여기서 판정을 재계산하거나 프롬프트 내용을 검열/가공하지 않는다
# — 프롬프트 설계(무엇을 넘길지)는 호출부(nodes.py/router.py) 책임이다.

import json
import os
import uuid
from typing import Any, Callable, Dict, List

CLOVASTUDIO_BASE_URL = "https://clovastudio.stream.ntruss.com"


def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 400) -> str:
    """CLOVASTUDIO_API_KEY로 CLOVA Studio(HyperCLOVA X)를 호출한다.

    키 미설정이면 RuntimeError — 호출부에서 잡아 폴백 문구를 쓴다. max_tokens는 호출부마다
    필요한 응답 길이가 달라(판정 요약은 짧게, 채팅 답변은 길게) 인자로 노출한다.
    """
    if not os.environ.get("CLOVASTUDIO_API_KEY"):
        raise RuntimeError("no LLM API key configured (CLOVASTUDIO_API_KEY)")
    return _call_clovastudio(system_prompt, user_prompt, max_tokens)


def _clovastudio_headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['CLOVASTUDIO_API_KEY']}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": uuid.uuid4().hex,
        "Content-Type": "application/json",
    }


def _call_clovastudio(system_prompt: str, user_prompt: str, max_tokens: int = 400) -> str:
    import requests

    model = os.environ.get("CLOVASTUDIO_MODEL", "HCX-005")
    response = requests.post(
        f"{CLOVASTUDIO_BASE_URL}/v3/chat-completions/{model}",
        headers=_clovastudio_headers(),
        json={
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "maxTokens": max_tokens,
        },
        timeout=15,
    )
    response.raise_for_status()
    return response.json()["result"]["message"]["content"].strip()


def call_llm_with_tools(
    system_prompt: str,
    user_prompt: str,
    tool_specs: List[Dict[str, Any]],
    tool_executor: Callable[[str, Dict[str, Any]], Any],
    max_tokens: int = 600,
    max_turns: int = 4,
) -> str:
    """CLOVA Studio Chat Completions v3의 실제 tool-calling 루프 — LLM이 스스로
    tool_executor를 호출하고, 그 반환값만 근거로 최종 자연어 답변을 만들게 한다
    (CLAUDE.md 절대 원칙 5: function calling 결과를 그대로 요약).

    tool_specs는 {"name", "description", "parameters"} 형태(OpenAI 호환 스키마)를
    기대하며, 이 함수가 CLOVA Studio의 {"type": "function", "function": {...}} 포맷으로
    감싼다. tool-calling은 max_tokens를 1024 이상으로 요구하므로 내부적으로 보정한다.
    """
    if not os.environ.get("CLOVASTUDIO_API_KEY"):
        raise RuntimeError("call_llm_with_tools requires CLOVASTUDIO_API_KEY")

    import requests

    model = os.environ.get("CLOVASTUDIO_MODEL", "HCX-005")
    tools = [
        {
            "type": "function",
            "function": {
                "name": spec["name"],
                "description": spec["description"],
                "parameters": spec["parameters"],
            },
        }
        for spec in tool_specs
    ]
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    for _ in range(max_turns):
        response = requests.post(
            f"{CLOVASTUDIO_BASE_URL}/v3/chat-completions/{model}",
            headers=_clovastudio_headers(),
            json={
                "messages": messages,
                "tools": tools,
                "maxTokens": max(max_tokens, 1024),
            },
            timeout=15,
        )
        response.raise_for_status()
        result = response.json()["result"]
        message = result["message"]

        if result.get("finishReason") != "tool_calls":
            return (message.get("content") or "").strip()

        messages.append(message)
        for call in message.get("toolCalls", []):
            fn = call["function"]
            tool_result = tool_executor(fn["name"], fn.get("arguments") or {})
            messages.append(
                {
                    "role": "tool",
                    "toolCallId": call["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

    raise RuntimeError("call_llm_with_tools: max_turns 안에 최종 답변을 얻지 못했다")
