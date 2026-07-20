# 법령 문서(국가공간정보 보안관리규정 등) 임베딩 및 벡터 인덱스 구축

from typing import List


def load_legal_documents(source_dir: str) -> List[str]:
    """법령 원문 문서를 읽어 텍스트 청크 리스트로 변환"""
    # TODO: source_dir 내 문서(pdf/txt 등) 로드 및 청킹
    raise NotImplementedError


def embed_and_index(chunks: List[str], index_path: str) -> None:
    """텍스트 청크를 임베딩하여 벡터 인덱스에 저장"""
    # TODO: 임베딩 모델 호출 후 벡터 스토어(FAISS 등)에 저장
    raise NotImplementedError
