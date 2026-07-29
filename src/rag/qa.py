# 법령 문서 기반 근거 조회 — RAG는 판정에 관여하지 않고, "왜 이 기준이 적용되는지" 설명할
# 때 인용할 근거 문장만 제공한다. superseded_by가 채워진 구버전 청크는 결과에서 제외한다.

from typing import Any, Dict, List

import chromadb

from src.rag.ingest import CHROMA_PERSIST_DIR, COLLECTION_NAME, ensure_indexed

_NOT_SUPERSEDED_FILTER = {"superseded_by": ""}


def _get_collection(persist_directory: str = CHROMA_PERSIST_DIR):
    ensure_indexed(persist_directory)
    client = chromadb.PersistentClient(path=persist_directory)
    return client.get_or_create_collection(COLLECTION_NAME)


def get_citations_for_facility(
    facility_id: str,
    regulation_theme: str = "default",
    top_k: int = 3,
    persist_directory: str = CHROMA_PERSIST_DIR,
) -> List[Dict[str, Any]]:
    """(facility_id, regulation_theme)로 최신(미대체) 조문 청크만 정확히 조회한다 — src.db
    구조화 DB와 동일한 키. 군사시설처럼 규정 테마가 여러 개인 시설은 regulation_theme을
    명시해야 그 테마에 해당하는 조문만 나온다.

    메타데이터 필터(facility_id + regulation_theme + superseded_by == "")만 사용하는 정확
    조회라, 임베딩 유사도와 무관하게 같은 키에는 항상 같은 근거 청크가 반환된다.
    """
    collection = _get_collection(persist_directory)
    result = collection.get(
        where={
            "$and": [
                {"facility_id": facility_id},
                {"regulation_theme": regulation_theme},
                _NOT_SUPERSEDED_FILTER,
            ]
        },
        limit=top_k,
    )
    return [
        {"chunk_id": chunk_id, "text": text, **metadata}
        for chunk_id, text, metadata in zip(result["ids"], result["documents"], result["metadatas"])
    ]


def retrieve_relevant_chunks(
    query: str, top_k: int = 5, persist_directory: str = CHROMA_PERSIST_DIR
) -> List[str]:
    """질의와 의미적으로 관련된 법령 조항 청크를 벡터 검색으로 조회한다 (구버전 청크는 제외)."""
    collection = _get_collection(persist_directory)
    result = collection.query(query_texts=[query], n_results=top_k, where=_NOT_SUPERSEDED_FILTER)
    return result["documents"][0] if result["documents"] else []


def answer_legal_question(query: str, index_path: str = CHROMA_PERSIST_DIR) -> str:
    """검색된 법령 조항을 근거로 자연어 답변 생성 (일반 법령 Q&A — 이번 작업 범위 밖)."""
    # TODO: retrieve_relevant_chunks 결과를 컨텍스트로 LLM 호출하여 답변 생성
    raise NotImplementedError
