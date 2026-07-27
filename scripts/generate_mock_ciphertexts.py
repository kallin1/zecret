# [Mock 관리기관 사전 준비 스크립트]
#
# 실제 환경에서는 이 스크립트 전체가 관리기관(국방부 등) 내부 시스템에서 실행되며,
# ZeCret 서비스는 암호문과 evaluation key(공개 컨텍스트)만 전달받아 동작합니다.
# 서비스 런타임(app.py, LangGraph 노드)은 이 스크립트를 절대 호출하지 않습니다 —
# 이미 만들어진 암호문 캐시(src/db/ciphertext_cache.db)와 공개 컨텍스트
# (src/he/public_context.bin)만 읽어서 사용합니다.
#
# 이 스크립트가 하는 일:
#   1. TenSEAL CKKS 컨텍스트 + 키 쌍(공개키/비밀키) 생성
#   2. 샘플 군사시설 Z값(높이제한 기준값, 평문)을 공개키로 암호화
#   3. ciphertext_blob을 암호문 캐시(src/db/ciphertext_cache.db)에 저장
#      (he_context_version, issued_at, expires_at, facility_id 함께 기록)
#   4. 비밀키 포함 컨텍스트는 scripts/keys/ 안에만 저장 (서비스 코드 어디에도 import 금지)
#   5. 공개 컨텍스트(evaluation key 포함)는 src/he/context.py가 읽을 수 있는 파일로 저장
#
# 사용법: python scripts/generate_mock_ciphertexts.py [--force]

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import tenseal as ts

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.ciphertext_cache import store_ciphertext  # noqa: E402
from src.he.context import HE_CONTEXT_VERSION, save_public_context  # noqa: E402

KEYS_DIR = Path(__file__).parent / "keys"
SECRET_CONTEXT_PATH = KEYS_DIR / "authority_secret_context.bin"

# CKKS 파라미터 — 작게 시작하되, 정밀도는 실측으로 검증한다 (CLAUDE.md 성능 지침).
#
# 이 서비스가 하는 연산은 (암호문 - 평문) 뺄셈 1회뿐이고 곱셈이 없으므로:
#   · relinearization/galois key는 생성하지 않는다 — 곱셈·회전 연산에만 필요하고
#     뺄셈에는 전혀 쓰이지 않는다. 이 두 키를 생략하는 것만으로 공개 컨텍스트 크기이
#     수십 배 줄어든다 (galois key 포함 시 컨텍스트 하나가 18MB, 생략 시 약 1MB).
#   · poly_modulus_degree=8192, coeff_mod_bit_sizes=[60, 40, 60] (총 160비트) — 128비트
#     보안 기준 N=8192의 최대 허용 비트 수(~218비트) 이내이면서, 뺄셈 1회 깊이에
#     필요한 레벨만 확보.
#
# 정밀도 검증: 처음에는 더 작은 N=4096/scale=2**21로 시작했으나, 실제 파일 직렬화 →
# 재로드 → 뺄셈 → 복호화 전 과정을 거치며 노이즈가 최대 ±0.002m(수 mm)까지 나타났고,
# 계획높이가 기준값과 정확히 같은 경계값(예: 45.0 == 45.0)에서 부호가 뒤집히는 사례를
# 실제로 재현했다. coeff_mod_bit_sizes/global_scale을 위 값으로 올려 20회 반복 측정한
# 결과 오차가 ~1e-9m(사실상 무시 가능) 수준으로 줄어 경계값 사례도 더 이상 뒤집히지
# 않음을 확인했다 — 부트스트래핑 없이 파라미터 조정만으로 해결됨 (CLAUDE.md 성능 지침).
POLY_MODULUS_DEGREE = 8192
COEFF_MOD_BIT_SIZES = [60, 40, 60]
GLOBAL_SCALE = 2**40

# 관리기관이 보유한 군사시설 비행안전구역 높이제한 기준값(Z값, 평문) — 이 스크립트
# 밖(서비스 코드 src/, app.py)에는 절대 등장하지 않는다. 실 데이터 연동 전까지는
# src.compliance.config의 MILITARY_ZONES 샘플 좌표와 짝을 맞춘 임의값이다.
_MILITARY_HEIGHT_LIMITS_PLAIN = {
    "military_seongnam_airport": 45.0,
}

_CIPHERTEXT_VALIDITY = timedelta(days=365)


def _build_authority_context() -> ts.Context:
    """[관리기관 전용] 비밀키를 포함한 전체 컨텍스트를 새로 만든다."""
    context = ts.context(
        ts.SCHEME_TYPE.CKKS,
        poly_modulus_degree=POLY_MODULUS_DEGREE,
        coeff_mod_bit_sizes=COEFF_MOD_BIT_SIZES,
    )
    context.global_scale = GLOBAL_SCALE
    return context


def generate_and_store_ciphertexts(force: bool = False) -> None:
    """CKKS 키 쌍을 생성하고, 샘플 군사시설 Z값을 암호화해 암호문 캐시에 저장한다.

    이미 생성되어 있으면(비밀 컨텍스트 파일 존재) 아무 것도 하지 않는다 — idempotent.
    force=True면 키를 새로 돌려 기존 암호문을 전부 무효화하고 다시 만든다.
    """
    if not force and SECRET_CONTEXT_PATH.exists():
        return

    KEYS_DIR.mkdir(parents=True, exist_ok=True)

    # 1) 관리기관 측 전체 컨텍스트(비밀키 포함) 생성
    authority_context = _build_authority_context()

    # 2) 비밀키 포함 컨텍스트는 scripts/keys/ 안에만 저장한다 — 서비스 코드는 이 경로를
    #    절대 import하지 않는다 (.gitignore에도 scripts/keys/가 등록되어 있어야 한다).
    with open(SECRET_CONTEXT_PATH, "wb") as f:
        f.write(authority_context.serialize(save_secret_key=True))

    # 3) 공개 컨텍스트(비밀키 제거본)는 서비스가 읽을 수 있도록 src/he/에 저장한다.
    #    copy() 이후에 make_context_public()을 호출해야, 비밀키가 필요한 authority_context
    #    자체는 그대로 남아 이후 암호화에 계속 쓸 수 있다.
    public_context = authority_context.copy()
    public_context.make_context_public()
    save_public_context(public_context.serialize())

    # 4) 샘플 Z값을 공개키로 암호화해 암호문 캐시(src/db/)에 저장한다.
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + _CIPHERTEXT_VALIDITY
    for facility_id, height_limit_plain in _MILITARY_HEIGHT_LIMITS_PLAIN.items():
        ciphertext_enc = ts.ckks_vector(authority_context, [height_limit_plain])
        store_ciphertext(
            facility_id=facility_id,
            ciphertext_blob=ciphertext_enc.serialize(),
            he_context_version=HE_CONTEXT_VERSION,
            issued_at=issued_at.isoformat(),
            expires_at=expires_at.isoformat(),
        )

    print(
        f"[generate_mock_ciphertexts] 암호문 캐시 준비 완료: "
        f"{list(_MILITARY_HEIGHT_LIMITS_PLAIN)} (he_context_version={HE_CONTEXT_VERSION})"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--force", action="store_true", help="이미 존재해도 키/암호문을 다시 생성한다 (기존 암호문 무효화)"
    )
    args = parser.parse_args()
    generate_and_store_ciphertexts(force=args.force)
