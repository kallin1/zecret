# LangGraph 노드 실행을 Langfuse span으로 기록하는 계측 래퍼.
#
# 노드 함수 내부 로직과 그래프 구조(노드/엣지)는 전혀 건드리지 않는다 — 그래프 조립
# 시점(build.py/runner.py)에서 각 노드 콜러블을 traced_node()로 감싸기만 한다.
#
# span에는 facility_id, regulation_type, latency_ms, exceeds_limit(bool)만 남긴다.
# 계획 높이 원본값(plan_height), 정확한 좌표(plan_x/plan_y), 이격거리(setback_distance),
# 암호문(diff_ciphertext) 등은 이 모듈을 거치는 순간부터 절대 span에 실리지 않는다
# (CLAUDE.md 절대 원칙 1 — allowlist 방식이라 새 민감 필드가 state에 추가돼도 여기서
# 명시적으로 추가하지 않는 한 자동으로 새어나가지 않는다).

import os
import time
from functools import wraps
from typing import Any, Callable, Dict, Optional

from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

_ALLOWED_OUTPUT_FIELDS = {"facility_id", "regulation_type", "latency_ms", "exceeds_limit"}

_client: Optional[Langfuse] = None
_client_initialized = False


def get_langfuse_client() -> Optional[Langfuse]:
    """LANGFUSE_PUBLIC_KEY/SECRET_KEY가 설정된 경우에만 클라이언트를 만든다.

    둘 다 없으면 트레이싱은 조용히 비활성화된다 — 이 환경(로컬 개발/테스트)처럼 자격증명이
    없을 때도 파이프라인 실행 자체는 막지 않기 위함이다.
    """
    global _client, _client_initialized
    if _client_initialized:
        return _client
    _client_initialized = True

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        _client = None
        return None

    _client = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com"),
    )
    return _client


def set_langfuse_client(client: Optional[Langfuse]) -> None:
    """[테스트 전용] 인메모리 span exporter 등으로 만든 클라이언트를 주입하거나, None으로
    되돌려 트레이싱을 다시 비활성화한다."""
    global _client, _client_initialized
    _client = client
    _client_initialized = True


def _redacted_input(state: Dict[str, Any]) -> Dict[str, Any]:
    """span 입력 — facility_id/regulation_type만 남긴다."""
    return {"facility_id": state.get("facility_id"), "regulation_type": state.get("facility_type")}


def _extract_exceeds_limit(result: Optional[Dict[str, Any]]) -> Optional[bool]:
    if not result:
        return None
    computation_result = result.get("computation_result")
    if computation_result:
        return computation_result.get("exceeds_limit")
    rag_verdict = result.get("rag_verdict")
    if rag_verdict:
        return rag_verdict.get("exceeds_limit")
    return None


def traced_node(node_fn: Callable[[Dict[str, Any]], Dict[str, Any]], node_name: str):
    """node_fn을 감싸 호출을 Langfuse span으로 기록한다.

    Langfuse가 설정되지 않은 경우 node_fn을 그대로 호출한다 (계측 유무와 무관하게 노드
    동작은 동일해야 한다).
    """

    @wraps(node_fn)
    def wrapped(state: Dict[str, Any]) -> Dict[str, Any]:
        client = get_langfuse_client()
        if client is None:
            return node_fn(state)

        redacted_input = _redacted_input(state)
        start = time.perf_counter()
        with client.start_as_current_observation(name=node_name, input=redacted_input) as span:
            try:
                result = node_fn(state)
            except Exception as exc:
                span.update(level="ERROR", status_message=str(exc))
                raise
            latency_ms = round((time.perf_counter() - start) * 1000, 2)
            output_fields = {
                **redacted_input,
                "latency_ms": latency_ms,
                "exceeds_limit": _extract_exceeds_limit(result),
            }
            assert set(output_fields) <= _ALLOWED_OUTPUT_FIELDS
            span.update(output=output_fields)
        return result

    return wrapped
