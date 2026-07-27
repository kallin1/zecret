# 참조 토큰 발급/검증 — "HE:{datasetId}:{buildingIndex}" 형식, 이 값으로 원본 재구성 불가 (체크포인트④)

import re

_TOKEN_PATTERN = re.compile(r"^HE:([^:]+):(\d+)$")


def issue_token(dataset_id: str, building_index: int) -> str:
    """클라이언트에 반환할 참조 토큰 발급 ("HE:{datasetId}:{buildingIndex}" 형식)"""
    return f"HE:{dataset_id}:{building_index}"


def parse_token(token: str) -> tuple:
    """토큰을 (dataset_id, building_index)로 파싱 — 원본 Z값 복원에는 사용 불가"""
    match = _TOKEN_PATTERN.match(token)
    if not match:
        raise ValueError(f"invalid token format: {token}")
    dataset_id, building_index = match.groups()
    return dataset_id, int(building_index)


def is_valid_token(token: str) -> bool:
    """토큰 형식이 유효한지 검증"""
    return bool(_TOKEN_PATTERN.match(token))
