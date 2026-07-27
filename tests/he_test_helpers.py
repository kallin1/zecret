# 테스트 전용 헬퍼 — 관리기관 비밀 컨텍스트로 임의의 평문 값을 암호화해 테스트 입력을
# 만든다. 서비스 코드(src/)에는 이런 "아무 값이나 암호화하는" 함수가 있으면 안 되고
# (비밀키를 서비스가 다루게 되므로), 오직 테스트가 "이미 암호화되어 들어온 입력값"을
# 재현하기 위한 용도로만 여기 존재한다.

import tenseal as ts

from scripts.generate_mock_ciphertexts import SECRET_CONTEXT_PATH, generate_and_store_ciphertexts
from src.he.encryption import HeightLimitCiphertext


def encrypt_for_test(height_limit_plain: float) -> HeightLimitCiphertext:
    """[테스트 전용] 관리기관 비밀 컨텍스트로 임의 평문 높이제한값을 암호화한다."""
    generate_and_store_ciphertexts()  # 비밀 컨텍스트 파일이 없으면 준비 (idempotent)
    with open(SECRET_CONTEXT_PATH, "rb") as f:
        authority_context = ts.context_from(f.read())
    ciphertext_enc = ts.ckks_vector(authority_context, [height_limit_plain])
    return HeightLimitCiphertext(ciphertext_enc=ciphertext_enc.serialize())
