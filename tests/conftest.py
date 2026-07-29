# 테스트 세션 시작 시 Mock 관리기관 준비 스크립트를 한 번 실행해, HE 관련 테스트가
# 필요로 하는 공개 컨텍스트(src/he/public_context.bin)·비밀 컨텍스트(scripts/keys/)·
# 암호문 캐시(src/db/ciphertext_cache.db)가 준비되어 있도록 한다. 이미 있으면 아무
# 것도 하지 않는다 (idempotent) — 신규 체크아웃에서도 별도 수동 셋업 없이 테스트가
# 그대로 돌아가게 하기 위함이다.
#
# 반드시 모듈 최상단(fixture 밖)에서 즉시 실행해야 한다 — src.compliance.config의
# MILITARY_ZONES는 모듈 import 시점에 그 순간의 ciphertext_cache.db 내용을 읽어 메모리에
# 고정한다. pytest는 각 테스트 파일을 import(collection)한 뒤에야 fixture를 실행하므로,
# 이 준비를 fixture 안에 두면 신규 체크아웃(비밀키 없음)에서 "collection 시점에 읽은
# 옛 암호문"과 "그 이후 fixture가 새로 생성한 비밀키"가 서로 어긋나 잘못된 키로 복호화하는
# 조용한 실패가 난다 — 로컬처럼 scripts/keys/가 이미 있으면(조기 반환) 드러나지 않는다.

import os

import pytest

# query_budget.py는 DEFAULT_QUERY_BUDGET을 모듈 import 시점에 한 번만 계산하므로, 로컬 .env에
# 데모용으로 낮춰둔 HE_QUERY_BUDGET_PER_REGULATION이 남아있으면 그 값이 테스트 전체에 고정돼
# 버린다(autouse 픽스처의 monkeypatch는 import 이후에 실행되어 되돌릴 수 없다). 그냥 지우기만
# 하면 소용없다 — 아래 import가 트리거하는 query_budget.py 자신의 load_dotenv() 호출이
# python-dotenv의 기본 동작(override=False, 즉 "os.environ에 없을 때만 채움")에 따라 .env
# 파일에서 다시 읽어 채워 넣기 때문이다. 그래서 지우는 대신 원래 하드코드 기본값(50)으로
# 미리 못박아, load_dotenv()가 이미 설정된 값을 건드리지 못하게 한다.
os.environ["HE_QUERY_BUDGET_PER_REGULATION"] = "50"

from scripts.generate_mock_ciphertexts import generate_and_store_ciphertexts
from src.security.query_budget import reset_query_budget

generate_and_store_ciphertexts()


@pytest.fixture(autouse=True)
def _reset_he_query_budget():
    """테스트마다 (facility_id, regulation_theme) 질의 카운터를 초기화한다.

    이 인메모리 카운터는 프로덕션 경로(src/graph, app.py)에서는 절대 리셋되지 않는다
    (query_budget.py 참고) — 여기서 리셋하지 않으면 한 테스트 세션 안에서 여러 테스트가
    같은 군사시설/규정 테마를 반복 호출하다 예산을 소진해, 실제로는 문제 없는 테스트가
    QueryBudgetExceededError로 실패하게 된다.
    """
    reset_query_budget()
    yield


@pytest.fixture(autouse=True)
def _no_real_llm_keys_by_default(monkeypatch):
    """테스트는 로컬 .env에 실제 CLOVASTUDIO_API_KEY가 들어있어도 그 키에 의존하면
    안 된다 — 매 테스트 전에 지워서 기본적으로 결정론적 폴백 경로를 타게 한다.
    특정 키가 설정된 상황을 검증하려는 테스트는 테스트 본문 안에서 직접
    monkeypatch.setenv()로 다시 설정하면 된다(이 fixture보다 나중에 실행되므로 덮어써진다).
    이게 없으면 개발자 로컬 .env 내용에 따라 테스트가 실제 네트워크 호출을 하게 되어
    느려지거나(quota 에러 재시도) 불안정해진다."""
    monkeypatch.delenv("CLOVASTUDIO_API_KEY", raising=False)
