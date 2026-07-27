# [Mock 관리기관 HSM 검증 API 대역]
#
# 실제 환경에서는 관리기관 HSM이 이 역할을 수행하며, 서비스는 diff_ciphertext만
# 전송하고 bool만 돌려받습니다. 서비스가 비밀키를 보유하지 않아야 한다는 원칙은 이
# 구조로 표현됩니다 — verify_diff()는 scripts/keys/의 비밀키를 이 파일 안에서만
# 로드하고, authority_verify_node(src/graph/nodes.py)는 이 함수를 "외부 API 호출
# 자리"로만 사용합니다. 서비스 코드(src/, app.py)는 이 파일이 비밀키를 어떻게 다루는지
# 알 필요가 없고, 실제로 몰라야 합니다.
#
# 실제 배포에서는 이 파일의 역할 전체가 관리기관 HSM API 엔드포인트 호출로 교체되어야
# 하며, scripts/keys/(비밀키)는 서비스와 같은 컨테이너/이미지에 포함되어서는 안 됩니다.
# 이 리포지토리는 별도의 HSM 서비스를 구축하는 대신, "비밀키를 다루는 코드는 scripts/
# 아래에만 있고 src/는 그 결과 bool만 받는다"는 경계로 그 원칙을 표현한 PoC입니다.

from pathlib import Path
from typing import List, Optional

import tenseal as ts

KEYS_DIR = Path(__file__).parent / "keys"
SECRET_CONTEXT_PATH = KEYS_DIR / "authority_secret_context.bin"

_secret_context: Optional[ts.Context] = None


def _load_secret_context() -> ts.Context:
    """[관리기관 전용] 비밀키가 포함된 컨텍스트를 로드한다. 이 함수 밖으로 절대 반환하지 않는다."""
    global _secret_context
    if _secret_context is not None:
        return _secret_context

    if not SECRET_CONTEXT_PATH.exists():
        raise FileNotFoundError(
            "관리기관 비밀 컨텍스트(scripts/keys/authority_secret_context.bin)가 없습니다. "
            "먼저 `python scripts/generate_mock_ciphertexts.py`를 실행하세요."
        )
    with open(SECRET_CONTEXT_PATH, "rb") as f:
        _secret_context = ts.context_from(f.read())
    return _secret_context


def verify_diff(diff_ciphertext_enc: bytes) -> bool:
    """diff 암호문(직렬화된 bytes)을 비밀키로 복호화해 부호(초과 여부)만 반환한다.

    diff = 높이제한(Z값) - 계획높이이므로, 음수면 초과(위반), 0 이상이면 미달(적합)이다.
    복호화한 정밀 수치(margin)는 이 함수 지역 변수 밖으로 절대 반환하지 않는다 —
    반환값은 bool 하나뿐이다 (CLAUDE.md 절대 원칙 1).
    """
    secret_context = _load_secret_context()
    diff_vector = ts.ckks_vector_from(secret_context, diff_ciphertext_enc)
    decrypted_diff = diff_vector.decrypt()[0]
    return decrypted_diff < 0


def verify_diff_batch(diff_ciphertexts_enc: List[bytes]) -> List[bool]:
    """[Phase 7 벤치마크 전용] 여러 diff 암호문을 한 번의 호출로 묶어 검증한다.

    실제 HSM API 환경이라면 이 배치화로 N번의 왕복을 1번으로 줄일 수 있다. 현재
    authority_verify_node(src/graph/nodes.py)는 요청 1건당 1개의 facility만 다루므로
    이 함수를 호출하지 않는다 — scripts/benchmark_he.py가 개별 verify_diff() N회 호출과
    비교 측정하는 용도로만 사용한다.
    """
    secret_context = _load_secret_context()
    results = []
    for diff_ciphertext_enc in diff_ciphertexts_enc:
        diff_vector = ts.ckks_vector_from(secret_context, diff_ciphertext_enc)
        results.append(diff_vector.decrypt()[0] < 0)
    return results
