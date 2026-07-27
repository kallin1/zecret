# 판정용 고정 참조 데이터 — 실 데이터(성남시 공간데이터 등) 연동 전까지 임의 좌표/값 유지.
# X, Y는 평문 취급 가능 (CLAUDE.md 원칙3). 군사시설 높이제한값은 암호문으로만 보관한다.
#
# 군사시설 높이제한 암호문은 이 파일에서 암호화하지 않는다 — 관리기관 역할의 오프라인
# 스크립트(scripts/generate_mock_ciphertexts.py)가 미리 암호화해 암호문 캐시(src/db/
# ciphertext_cache.py)에 저장해 둔 것을 여기서는 조회만 한다. 그래서 이 파일에는 군사
# 시설 높이제한의 평문 값이 등장하는 지점이 전혀 없다 (CLAUDE.md 절대 원칙 1).

from dataclasses import dataclass, field
from typing import List

from src.db.ciphertext_cache import load_ciphertext
from src.he.encryption import HeightLimitCiphertext, load_height_limit_ciphertext

# 일조권 사선제한 (건축법 제61조, 시행령 제86조)
SUNLIGHT_SETBACK_HEIGHT_THRESHOLD_M = 9.0
SUNLIGHT_SETBACK_LOW_RISE_MIN_DISTANCE_M = 1.5

# 계획 건물 위치 기준 이 반경(m) 안에 있는 유산/시설만 "인접"으로 보고 판정 대상에 포함한다.
ADJACENCY_RADIUS_M = 1_000.0


@dataclass
class HeritageSite:
    """국가유산 역사문화환경보존지역 1건 — 허용높이는 유산별 개별 고시 수치(평문 취급).

    facility_id는 src.db(구조화 기준값 DB)의 동일 facility_id 행과 대조하는 데 쓰인다.
    """

    facility_id: str
    name: str
    x_plain: float
    y_plain: float
    allowed_height_m: float


@dataclass
class MilitaryZone:
    """군사시설 비행안전구역 1건 — height_limit_enc만 z값 비공개 대상 (CLAUDE.md 원칙1·2).

    facility_id는 src.db(구조화 기준값 DB)의 동일 facility_id 행과 대조하는 데 쓰인다.
    """

    facility_id: str
    name: str
    x_plain: float
    y_plain: float
    height_limit_enc: HeightLimitCiphertext = field(repr=False)


# TODO: 문화재보호법상 실제 고시 수치로 교체 예정 — 현재는 좌표/허용높이 모두 샘플값.
# facility_id는 src/db 구조화 기준값 DB의 heritage_namhansanseong 행과 짝을 맞춘다.
HERITAGE_SITES: List[HeritageSite] = [
    HeritageSite(
        facility_id="heritage_namhansanseong",
        name="남한산성 역사문화환경보존지역",
        x_plain=127.123456,
        y_plain=37.124123,
        allowed_height_m=15.0,
    ),
]

def _load_military_ciphertext(facility_id: str) -> HeightLimitCiphertext:
    """암호문 캐시(src.db.ciphertext_cache)에서 facility_id의 높이제한 암호문을 읽어온다.

    캐시가 비어 있으면(스크립트 미실행) 여기서 바로 실패시킨다 — 서비스가 평문 기본값
    등으로 조용히 대체하는 일이 없도록 하기 위함이다 (CLAUDE.md 절대 원칙 1).
    """
    row = load_ciphertext(facility_id)
    if row is None:
        raise RuntimeError(
            f"'{facility_id}'의 암호문 캐시가 없습니다. 먼저 "
            "`python scripts/generate_mock_ciphertexts.py`를 실행해 암호문 캐시를 준비하세요."
        )
    return load_height_limit_ciphertext(row["ciphertext_blob"])


# TODO: 군사기지 및 군사시설 보호법상 실제 비행안전구역 고시 수치로 교체 예정 — 현재는 좌표만 샘플값.
# facility_id는 src/db 구조화 기준값 DB 및 암호문 캐시의 military_seongnam_airport 행과 짝을 맞춘다.
MILITARY_ZONES: List[MilitaryZone] = [
    MilitaryZone(
        facility_id="military_seongnam_airport",
        name="성남 서울공항 비행안전구역",
        x_plain=127.125000,
        y_plain=37.126000,
        height_limit_enc=_load_military_ciphertext("military_seongnam_airport"),
    ),
]
