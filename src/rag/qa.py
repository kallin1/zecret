# 법령 문서 기반 질의응답 — 벡터 검색으로 관련 조항을 찾아 근거 기반 답변 생성

from typing import List


def retrieve_relevant_chunks(query: str, index_path: str, top_k: int = 5) -> List[str]:
    """질의와 관련된 법령 조항 청크를 벡터 검색으로 조회"""
    # TODO: index_path의 벡터 인덱스에서 유사도 검색 수행
    raise NotImplementedError


def answer_legal_question(query: str, index_path: str) -> str:
    """검색된 법령 조항을 근거로 자연어 답변 생성"""
    # TODO: retrieve_relevant_chunks 결과를 컨텍스트로 LLM 호출하여 답변 생성
    raise NotImplementedError
