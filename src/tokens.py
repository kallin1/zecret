# 참조 토큰 발급/검증 — "HE:{datasetId}:{referenceId}" 형식, 이 값으로 원본 재구성 불가 (체크포인트④)
#
# 애초 설계는 "HE:{datasetId}:{buildingIndex}"(정수 인덱스)였지만, 이 프로젝트의 실제 HE
# 대상 키는 (facility_id, regulation_theme) 복합키(src.db.ciphertext_cache 참고)라 "building"
# 개념 자체가 없다. referenceId를 정수로 강제하지 않고 regulation_theme 같은 기존 도메인
# 키를 그대로 받는다 — facility_id/regulation_theme는 원본 Z값과 수학적으로 무관한 메타데이터라
# 토큰만으로 원본을 복원할 수 없다는 보장은 그대로 유지된다.

import re

_TOKEN_PATTERN = re.compile(r"^HE:([^:]+):([^:]+)$")


def issue_token(dataset_id: str, reference_id: str) -> str:
    """클라이언트에 반환할 참조 토큰 발급 ("HE:{datasetId}:{referenceId}" 형식)"""
    return f"HE:{dataset_id}:{reference_id}"


def parse_token(token: str) -> tuple:
    """토큰을 (dataset_id, reference_id)로 파싱 — 원본 Z값 복원에는 사용 불가"""
    match = _TOKEN_PATTERN.match(token)
    if not match:
        raise ValueError(f"invalid token format: {token}")
    return match.group(1), match.group(2)


def is_valid_token(token: str) -> bool:
    """토큰 형식이 유효한지 검증"""
    return bool(_TOKEN_PATTERN.match(token))
