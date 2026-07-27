# 서비스가 사용하는 CKKS "공개" 컨텍스트(공개키만, 비밀키 없음) 로더/저장소.
#
# 이 공개 컨텍스트는 scripts/generate_mock_ciphertexts.py(관리기관 역할의 오프라인
# 스크립트)가 비밀키 컨텍스트에서 make_context_public()으로 비밀키를 제거해 만든 뒤
# 여기(파일)로 저장해 둔 것을 이 모듈이 읽기만 한다. 이 파일은 비밀키를 만들거나
# 다루지 않는다 — 서비스 코드(src/, app.py) 전체에서 비밀키를 import하지 않는다는
# 원칙이 지켜지는 경계가 바로 이 모듈이다 (CLAUDE.md 절대 원칙 1).
#
# public_context.bin에는 evaluation key(이 서비스가 필요로 하는 연산 — 암호문/평문
# 뺄셈 — 에는 galois/relinearization 키가 필요 없어 포함하지 않는다. 자세한 이유는
# scripts/generate_mock_ciphertexts.py 참고)까지 포함되어 있어, he_compute_node가
# 이 컨텍스트 하나만으로 동형 뺄셈을 수행할 수 있다.

from pathlib import Path
from typing import Optional

import tenseal as ts

# scripts/generate_mock_ciphertexts.py가 암호문 캐시 행에 기록하는 버전 태그와 동일해야
# 한다 — CKKS 파라미터를 바꿔 컨텍스트를 재생성하면 이 값도 함께 올린다.
HE_CONTEXT_VERSION = "ckks-v1"

_CONTEXT_PATH = Path(__file__).parent / "public_context.bin"

_cached_context: Optional[ts.Context] = None


def save_public_context(context_bytes: bytes) -> None:
    """[생성 스크립트 전용] 공개 컨텍스트(비밀키 없음) bytes를 서비스가 읽을 파일로 저장한다.

    호출부(scripts/generate_mock_ciphertexts.py)가 비밀키를 제거한 컨텍스트만 넘긴다는
    것을 책임진다 — 이 함수 자체는 비밀키 유무를 알지 못한 채 그대로 파일에 쓴다.
    """
    _CONTEXT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_CONTEXT_PATH, "wb") as f:
        f.write(context_bytes)


def load_public_context() -> ts.Context:
    """공개 컨텍스트를 로드한다. 프로세스 안에서 한 번만 역직렬화하고 캐시해 재사용한다."""
    global _cached_context
    if _cached_context is not None:
        return _cached_context

    if not _CONTEXT_PATH.exists():
        raise FileNotFoundError(
            "공개 컨텍스트(src/he/public_context.bin)가 없습니다. "
            "먼저 `python scripts/generate_mock_ciphertexts.py`를 실행해 암호문 캐시와 "
            f"공개 컨텍스트를 준비하세요. (찾은 경로: {_CONTEXT_PATH})"
        )

    with open(_CONTEXT_PATH, "rb") as f:
        context_bytes = f.read()
    context = ts.context_from(context_bytes)

    if context.has_secret_key():
        # 방어적 점검 — 공개 컨텍스트 파일에 비밀키가 섞여 저장된 경우 서비스가 그대로
        # 쓰지 않도록 즉시 실패시킨다 (CLAUDE.md 절대 원칙 1).
        raise RuntimeError(
            "public_context.bin에 비밀키가 포함되어 있습니다 — "
            "scripts/generate_mock_ciphertexts.py의 make_context_public() 호출을 점검하세요."
        )

    _cached_context = context
    return _cached_context
