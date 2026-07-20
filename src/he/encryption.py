# CKKS 기반 Z값(높이) 암호화/복호화 — 서버 내부 전용, 복호화 결과가 이 모듈 밖으로 평문으로 나가면 안 됨

from typing import Any, List


class CkksContext:
    """CKKS 암호화 파라미터/키를 보관하는 컨텍스트 (Pyfhel 또는 OpenFHE 래퍼)"""
    # TODO: Pyfhel(또는 OpenFHE) 컨텍스트 초기화. 파라미터는 작게 시작하고 필요 시에만 부트스트래핑 고려.
    pass


def create_context() -> CkksContext:
    """CKKS 컨텍스트(파라미터+키) 생성"""
    # TODO: 암호화 파라미터(poly_modulus_degree, scale 등) 설정 후 키 생성
    raise NotImplementedError


def encrypt_z(z_plain: float, ctx: CkksContext) -> Any:
    """단일 Z값(높이, 평문)을 CKKS 암호문으로 암호화"""
    # TODO: ctx를 이용해 z_plain을 암호화하여 ciphertext 반환
    raise NotImplementedError


def encrypt_z_batch(z_plain_list: List[float], ctx: CkksContext) -> Any:
    """여러 Z값을 벡터화하여 배치 암호화 (행렬 연산 활용 권장)"""
    # TODO: z_plain_list를 벡터로 묶어 암호화 (바이너리 단위 연산 대신 벡터 연산 우선 검토)
    raise NotImplementedError


def _decrypt_z_internal(z_enc: Any, ctx: CkksContext) -> float:
    """[서버 내부 전용] 암호문을 복호화하여 평문 Z값 반환.

    주의: 이 함수의 반환값은 he/compare.py 등 서버 내부 판정 로직에서만 사용해야 하며,
    API 응답/로그/프론트엔드로 절대 그대로 전달하면 안 됨 (CLAUDE.md 절대 원칙 1).
    """
    # TODO: ctx를 이용해 z_enc를 복호화
    raise NotImplementedError
