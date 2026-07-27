# 군사시설 비행안전구역 고도제한 기준값(Z값) — 실제 TenSEAL CKKS 암호문 연산.
#
# 이 파일은 "서비스가 비밀키를 보유하지 않는다"는 CLAUDE.md 절대 원칙 1을 코드로
# 강제하는 경계다: 여기서 다루는 모든 값은 _enc 접미사가 붙은 암호문뿐이고, 평문 Z값이
# 등장하는 지점이 전혀 없다. 복호화(비밀키 필요)는 이 파일 어디에도 없으며,
# scripts/mock_authority_verify.py(관리기관 HSM 자리) 안에서만 일어난다.
#
# 암호문(ciphertext_enc/diff_enc)은 항상 "직렬화된 bytes"로 다룬다 — 실제로 관리기관
# HSM에 네트워크로 전송할 값과 동일한 형태를 이 프로세스 안에서도 유지하기 위함이다.

from dataclasses import dataclass, field

import tenseal as ts

from src.he.context import load_public_context


@dataclass
class HeightLimitCiphertext:
    """군사시설 높이제한 기준값(Z값)의 CKKS 암호문 — 직렬화된 bytes만 담는다.

    scripts/generate_mock_ciphertexts.py(관리기관 오프라인 스크립트)가 비밀키로 암호화해
    src.db.ciphertext_cache에 저장해 둔 것을, 서비스(src.compliance.config)가 그대로
    읽어와 감싼 값이다. 이 객체 안에는 평문 필드가 전혀 없다.
    """

    ciphertext_enc: bytes = field(repr=False)


def load_height_limit_ciphertext(ciphertext_blob: bytes) -> HeightLimitCiphertext:
    """암호문 캐시(src.db.ciphertext_cache)에서 읽은 opaque bytes를 그대로 감싼다.

    복호화하지 않는다 — 이 함수는 단순히 캐시에서 읽은 bytes를 타입이 있는 객체로
    감싸기만 한다.
    """
    return HeightLimitCiphertext(ciphertext_enc=ciphertext_blob)


@dataclass
class DiffCiphertext:
    """(높이제한 암호문 - 계획높이 평문) 동형 뺄셈 결과의 직렬화된 bytes.

    서비스는 이 값을 복호화하지 않는다 — 부호(초과 여부) 확인은 이 bytes를
    scripts.mock_authority_verify.verify_diff()(관리기관 HSM 자리)로 전송해서만 받는다
    (CLAUDE.md 절대 원칙 1).
    """

    diff_enc: bytes = field(repr=False)


def compute_diff_ciphertext(
    height_limit: HeightLimitCiphertext, plan_height_plain: float
) -> DiffCiphertext:
    """암호문(높이제한 Z값) - 평문(계획높이)의 동형 뺄셈 — 공개 컨텍스트(비밀키 없음)만 사용.

    TenSEAL CKKS의 ciphertext-plaintext 뺄셈은 비밀키 없이 공개 컨텍스트만으로 계산
    가능하다 (곱셈이 아니므로 relinearization/galois 키도 필요 없다 — 파라미터 선정
    근거는 scripts/generate_mock_ciphertexts.py 참고). 이 함수는 diff를 복호화하지
    않고 그대로 직렬화해 반환한다.
    """
    public_context = load_public_context()
    height_limit_vec = ts.ckks_vector_from(public_context, height_limit.ciphertext_enc)
    diff_vec = height_limit_vec - plan_height_plain
    return DiffCiphertext(diff_enc=diff_vec.serialize())
