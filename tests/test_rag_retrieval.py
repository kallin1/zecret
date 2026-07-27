# RAG 벡터DB(src/rag) — facility_id 기반 근거 조회 검증.
# Phase 4 완료 기준: facility_id로 쿼리하면 관련 조문 청크가 검색된다 (LLM 미연결 상태로 확인).
# RAG는 판정에 관여하지 않는 근거 인용 전용이므로, 여기서는 exceeds_limit/margin을 다루지 않는다.

import pytest

from src.rag.qa import get_citations_for_facility, retrieve_relevant_chunks


@pytest.mark.parametrize(
    "facility_id",
    ["military_seongnam_airport", "heritage_namhansanseong", "sunlight_setback_general"],
)
def test_get_citations_for_facility_returns_chunks(facility_id):
    citations = get_citations_for_facility(facility_id)
    assert citations
    for c in citations:
        assert c["facility_id"] == facility_id
        assert c["text"]


def test_superseded_chunk_excluded_from_facility_lookup():
    """건축법 제61조 구버전(1999) 청크는 superseded_by가 채워져 있어 검색에서 빠지고,
    현행(2016 개정) 청크만 나와야 한다."""
    citations = get_citations_for_facility("sunlight_setback_general")
    chunk_ids = {c["chunk_id"] for c in citations}
    assert "sunlight_setback_building_act_61_v2" in chunk_ids
    assert "sunlight_setback_building_act_61_v1" not in chunk_ids


def test_citations_never_carry_superseded_marker_for_current_chunk():
    citations = get_citations_for_facility("heritage_namhansanseong")
    for c in citations:
        assert c["superseded_by"] == ""


def test_military_citation_never_mentions_numeric_height():
    """군사시설 근거 조문은 고도제한이 비공개라는 사실만 서술하고, 구체적 수치를 담지
    않아야 한다 (CLAUDE.md 절대 원칙 1) — 45(현재 샘플 height_limit_m)가 텍스트에 없는지 확인."""
    citations = get_citations_for_facility("military_seongnam_airport")
    for c in citations:
        assert "45" not in c["text"]


def test_unknown_facility_id_returns_empty():
    citations = get_citations_for_facility("does_not_exist")
    assert citations == []


def test_retrieve_relevant_chunks_semantic_search():
    chunks = retrieve_relevant_chunks("군사시설 비행안전구역 높이 제한", top_k=2)
    assert chunks
    assert any("군사기지" in c or "비행안전구역" in c for c in chunks)


def test_retrieve_relevant_chunks_excludes_superseded():
    chunks = retrieve_relevant_chunks("건축법 제61조 일조권 이격거리", top_k=5)
    assert not any("1999" in c for c in chunks)
