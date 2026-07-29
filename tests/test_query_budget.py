# 반복 질의 기반 오라클 방어(src/security/query_budget.py, docs/oracle_defense.md) 검증.
# 핵심 확인 사항: (1) (facility_id, regulation_theme) 조합별로 독립적으로 예산이 걸리고
# 넘기면 거부되는가, (2) authority_verify_node가 예산 초과 시 exceeds_limit을 임의로
# 지어내지 않고 예외를 그대로 던지는가(CLAUDE.md 절대 원칙 1과 직결).

import pytest

from src.compliance.config import MILITARY_ZONES
from src.graph.nodes import authority_verify_node
from src.he.encryption import compute_diff_ciphertext
from src.security.query_budget import (
    DEFAULT_QUERY_BUDGET,
    QueryBudgetExceededError,
    consume_query_budget,
    get_query_count,
    reset_query_budget,
)
from tests.he_test_helpers import encrypt_for_test


def test_budget_allows_up_to_limit_then_raises():
    for _ in range(3):
        consume_query_budget("facility_a", "theme_x", budget=3)

    with pytest.raises(QueryBudgetExceededError) as exc_info:
        consume_query_budget("facility_a", "theme_x", budget=3)

    assert exc_info.value.facility_id == "facility_a"
    assert exc_info.value.regulation_theme == "theme_x"
    assert exc_info.value.query_count == 4  # Langfuse span에 그대로 실리는 값 (tracing.py)
    assert exc_info.value.budget == 3
    assert get_query_count("facility_a", "theme_x") == 4  # 초과 호출도 카운트에는 반영됨


def test_budget_tracks_facility_and_theme_independently():
    consume_query_budget("facility_a", "protect_zone", budget=2)
    consume_query_budget("facility_a", "protect_zone", budget=2)
    consume_query_budget("facility_a", "flight_safety", budget=2)  # 다른 테마는 별개 예산

    assert get_query_count("facility_a", "protect_zone") == 2
    assert get_query_count("facility_a", "flight_safety") == 1

    with pytest.raises(QueryBudgetExceededError):
        consume_query_budget("facility_a", "protect_zone", budget=2)


def test_reset_clears_all_counters():
    consume_query_budget("facility_a", "theme_x", budget=10)
    assert get_query_count("facility_a", "theme_x") == 1

    reset_query_budget()

    assert get_query_count("facility_a", "theme_x") == 0
    consume_query_budget("facility_a", "theme_x", budget=1)  # 리셋 후엔 다시 1회부터 허용


def test_authority_verify_node_raises_without_fabricating_result():
    """예산 초과 시 authority_verify_node는 computation_result를 만들어내지 않고 그대로 예외를 던진다."""
    zone = MILITARY_ZONES[0]
    regulation = zone.regulations[0]
    diff_ciphertext = compute_diff_ciphertext(encrypt_for_test(45.0), 30.0)
    state = {
        "facility_id": zone.facility_id,
        "regulation_theme": regulation.theme_id,
        "diff_ciphertext": diff_ciphertext,
    }

    # authority_verify_node는 기본 예산(DEFAULT_QUERY_BUDGET)으로 consume_query_budget을
    # 호출하므로, 그 한도만큼 미리 소진시켜 다음 1회 호출이 초과하도록 만든다.
    for _ in range(DEFAULT_QUERY_BUDGET):
        consume_query_budget(zone.facility_id, regulation.theme_id, budget=DEFAULT_QUERY_BUDGET)

    with pytest.raises(QueryBudgetExceededError):
        authority_verify_node(state)


def test_authority_verify_node_surfaces_query_count_on_success():
    """정상 판정 시 반환값에 he_query_count(순수 카운터)가 담겨 traced_node가 Langfuse에 실을 수 있다."""
    zone = MILITARY_ZONES[0]
    regulation = zone.regulations[0]
    diff_ciphertext = compute_diff_ciphertext(encrypt_for_test(45.0), 30.0)
    state = {
        "facility_id": zone.facility_id,
        "regulation_theme": regulation.theme_id,
        "diff_ciphertext": diff_ciphertext,
    }

    result = authority_verify_node(state)

    assert result["he_query_count"] == 1
    result_again = authority_verify_node(state)
    assert result_again["he_query_count"] == 2
