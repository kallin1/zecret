# src/graph/tracing.py — Langfuse span 계측의 redact 보장 검증.
# 실제 Langfuse 자격증명 없이도 검증할 수 있도록, 네트워크로 나가는 실제 exporter 대신
# OpenTelemetry의 InMemorySpanExporter를 주입해 이 프로세스 안에서 span을 직접 캡처한다.
#
# 완료 기준(Phase 5): 노드별 span이 남고, 민감 필드(plan_height 원본값·정확한 좌표·
# 암호문)는 마스킹되어 span에 절대 등장하지 않으며, 남는 필드는 facility_id/
# regulation_type/latency_ms/exceeds_limit 뿐이다.

import json

import pytest
from langfuse import Langfuse
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from src.graph.tracing import set_langfuse_client, traced_node
from src.security.query_budget import QueryBudgetExceededError


class _CapturedSpans:
    """InMemorySpanExporter를 감싸, 조회 전 client.flush()로 강제 export하는 헬퍼."""

    def __init__(self, client: Langfuse, exporter: InMemorySpanExporter):
        self._client = client
        self._exporter = exporter

    def get_finished_spans(self):
        self._client.flush()
        return self._exporter.get_finished_spans()


# OpenTelemetry의 전역 TracerProvider는 프로세스당 한 번만 등록되므로(Langfuse 인스턴스를
# 여러 번 새로 만들어도 두 번째부터는 exporter가 실제로 연결되지 않는다), 이 파일의 모든
# 테스트가 세션 범위로 exporter/client 하나를 공유하고 매 테스트 전에 clear()만 한다.
@pytest.fixture(scope="session")
def _shared_langfuse_exporter():
    exporter = InMemorySpanExporter()
    client = Langfuse(
        public_key="pk-test",
        secret_key="sk-test",
        host="http://localhost:1",  # 실제로는 절대 연결되지 않음 — span_exporter가 네트워크를 대체
        span_exporter=exporter,
    )
    return client, exporter


@pytest.fixture
def captured_spans(_shared_langfuse_exporter):
    client, exporter = _shared_langfuse_exporter
    exporter.clear()
    set_langfuse_client(client)
    try:
        yield _CapturedSpans(client, exporter)
    finally:
        set_langfuse_client(None)


_SENSITIVE_STATE = {
    "facility_type": "military",
    "facility_id": "military_seongnam_airport",
    "facility_name": "성남 서울공항 비행안전구역",
    "plan_x": 127.125000,
    "plan_y": 37.126000,
    "plan_height": 123.456,
    "setback_distance": 3.0,
    "diff_ciphertext": object(),
}


def _dummy_node(state):
    return {"computation_result": {"exceeds_limit": True, "margin": None}}


def _span_text_blob(span) -> str:
    """이 span에 실린 모든 attribute 값을 문자열 하나로 합친다 (민감값 부재를 스캔하기 위함)."""
    return json.dumps({k: str(v) for k, v in span.attributes.items()}, ensure_ascii=False)


def test_traced_node_creates_one_span_per_call(captured_spans):
    wrapped = traced_node(_dummy_node, "he_compute")
    wrapped(_SENSITIVE_STATE)
    spans = captured_spans.get_finished_spans()
    assert len(spans) == 1
    assert spans[0].name == "he_compute"


def test_span_never_contains_sensitive_fields(captured_spans):
    wrapped = traced_node(_dummy_node, "he_compute")
    wrapped(_SENSITIVE_STATE)
    span = captured_spans.get_finished_spans()[0]
    blob = _span_text_blob(span)

    assert "123.456" not in blob  # plan_height 원본값
    assert "127.125" not in blob  # 정확한 좌표(경도)
    assert "37.126" not in blob  # 정확한 좌표(위도)
    assert "diff_ciphertext" not in blob
    assert "setback_distance" not in blob
    assert "plan_height" not in blob
    assert "plan_x" not in blob
    assert "plan_y" not in blob


def test_span_output_only_has_allowed_fields(captured_spans):
    wrapped = traced_node(_dummy_node, "he_compute")
    wrapped(_SENSITIVE_STATE)
    span = captured_spans.get_finished_spans()[0]
    output = json.loads(span.attributes["langfuse.observation.output"])

    assert set(output.keys()) == {"facility_id", "regulation_type", "latency_ms", "exceeds_limit"}
    assert output["facility_id"] == "military_seongnam_airport"
    assert output["regulation_type"] == "military"
    assert output["exceeds_limit"] is True
    assert isinstance(output["latency_ms"], (int, float))


def test_node_return_value_unaffected_by_tracing(captured_spans):
    """계측 유무와 무관하게 노드의 반환값(state 업데이트)은 그대로여야 한다."""
    wrapped = traced_node(_dummy_node, "he_compute")
    result = wrapped(_SENSITIVE_STATE)
    assert result == {"computation_result": {"exceeds_limit": True, "margin": None}}


def test_span_includes_query_count_when_node_reports_it(captured_spans):
    """authority_verify_node처럼 he_query_count를 반환하는 노드는 span output에도 그대로 실린다."""

    def _node_with_query_count(state):
        return {"computation_result": {"exceeds_limit": True, "margin": None}, "he_query_count": 7}

    wrapped = traced_node(_node_with_query_count, "authority_verify")
    wrapped(_SENSITIVE_STATE)
    # 앞선 테스트(test_node_return_value_unaffected_by_tracing)가 flush()를 호출하지 않아
    # 그 span이 배치 프로세서에 남아있다가 이번 flush에 함께 밀려나올 수 있다 — [0]이 아니라
    # 이름으로 골라야 안전하다.
    span = next(s for s in captured_spans.get_finished_spans() if s.name == "authority_verify")
    output = json.loads(span.attributes["langfuse.observation.output"])

    assert output["query_count"] == 7
    assert set(output.keys()) == {"facility_id", "regulation_type", "latency_ms", "exceeds_limit", "query_count"}


def test_budget_exceeded_marks_span_error_with_structured_counts(captured_spans):
    """QueryBudgetExceededError는 span을 ERROR로 마킹하고 query_count/query_budget을 구조화된
    output으로 남긴다 — Langfuse에서 facility_id/regulation_type으로 필터링해 오라클 probing
    시도를 다른 정상 판정과 구분해 볼 수 있어야 한다."""

    def _budget_exceeded_node(state):
        raise QueryBudgetExceededError("military_seongnam_airport", "protect_zone", budget=50, query_count=51)

    wrapped = traced_node(_budget_exceeded_node, "authority_verify")
    with pytest.raises(QueryBudgetExceededError):
        wrapped(_SENSITIVE_STATE)

    span = next(s for s in captured_spans.get_finished_spans() if s.name == "authority_verify")
    assert span.attributes["langfuse.observation.level"] == "ERROR"
    output = json.loads(span.attributes["langfuse.observation.output"])
    assert output["query_count"] == 51
    assert output["query_budget"] == 50
    assert output["facility_id"] == "military_seongnam_airport"


def test_tracing_disabled_when_no_langfuse_client():
    """Langfuse 클라이언트가 없으면(자격증명 미설정) 노드를 그냥 직접 호출한다 — 계측이
    파이프라인 실행 자체를 막아서는 안 된다."""
    set_langfuse_client(None)
    wrapped = traced_node(_dummy_node, "he_compute")
    result = wrapped(_SENSITIVE_STATE)
    assert result == {"computation_result": {"exceeds_limit": True, "margin": None}}
