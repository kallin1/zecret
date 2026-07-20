# 참조 토큰 발급/검증 — "HE:{datasetId}:{buildingIndex}" 형식, 이 값으로 원본 재구성 불가 (체크포인트④)


def issue_token(dataset_id: str, building_index: int) -> str:
    """클라이언트에 반환할 참조 토큰 발급 ("HE:{datasetId}:{buildingIndex}" 형식)"""
    # TODO: dataset_id, building_index로 토큰 문자열 생성 (원본 값/암호문 자체는 포함 금지)
    raise NotImplementedError


def parse_token(token: str) -> tuple:
    """토큰을 (dataset_id, building_index)로 파싱 — 원본 Z값 복원에는 사용 불가"""
    # TODO: "HE:{datasetId}:{buildingIndex}" 형식 파싱 및 유효성 검증
    raise NotImplementedError


def is_valid_token(token: str) -> bool:
    """토큰 형식이 유효한지 검증"""
    # TODO: 정규식 등으로 형식 검증
    raise NotImplementedError
