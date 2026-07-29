# 판정용 참조 데이터 — 공개제한(군사시설) 앵커는 성남시 실재 시설(서울공항/성남비행장,
# 공군 제15특수임무비행단)로 접지했다. 좌표는 항공정보간행물(AIP) 공개 기준점(ARP)/
# 지하철역명 등 이미 공개된 랜드마크 수준 근사치이며, 활주로 등 정밀 시설 좌표가 아니다.
# X, Y는 평문 취급 가능 (CLAUDE.md 원칙3). 군사시설 높이제한값(Z)만 암호문으로만 보관한다.
#
# 군사시설 높이제한 암호문은 이 파일에서 암호화하지 않는다 — 관리기관 역할의 오프라인
# 스크립트(scripts/generate_mock_ciphertexts.py)가 미리 암호화해 암호문 캐시(src/db/
# ciphertext_cache.py)에 저장해 둔 것을 여기서는 조회만 한다. 그래서 이 파일에는 군사
# 시설 높이제한의 평문 값이 등장하는 지점이 전혀 없다 (CLAUDE.md 절대 원칙 1).
#
# 군사시설은 중첩되는 두 개의 법적 근거(규정 테마)를 동시에 가질 수 있다 — 서울공항은
# 군사기지 및 군사시설 보호법 제9조(제한보호구역 일반 고도제한)와 제10조(비행안전구역
# 기본표면)가 함께 적용되므로, MilitaryZone.regulations에 테마별로 별도 암호문을 둔다.

from dataclasses import dataclass, field
from typing import List, Optional

from src.db.ciphertext_cache import load_ciphertext
from src.he.encryption import HeightLimitCiphertext, load_height_limit_ciphertext

# 일조권 사선제한 (건축법 제61조, 시행령 제86조)
SUNLIGHT_SETBACK_HEIGHT_THRESHOLD_M = 9.0
SUNLIGHT_SETBACK_LOW_RISE_MIN_DISTANCE_M = 1.5

# 국가유산 등 "인접" 판정에 쓰는 기본 반경(m) — 시설 유형별 반경 테이블(아래
# ZONE_RADIUS_BY_SUBTYPE)이 없는 카테고리(문화재 등)는 이 값을 그대로 쓴다.
ADJACENCY_RADIUS_M = 1_000.0

# 군사기지 및 군사시설 보호법 제5조(보호구역의 지정범위) 근거 — 시설 유형(zone_subtype)별
# 제한보호구역 지정범위(m). 검색 스니펫 경유로 확인한 수치라 실 구현 시 시행령 제5조 원문
# (별표) 대조로 재검증이 필요하다. 이 반경 수치 자체는 법령상 공개 정보이므로 평문으로
# 다뤄도 무방하다 — 비공개 대상은 각 구역의 "높이(Z)" 기준값뿐이다 (CLAUDE.md 원칙 1·3).
ZONE_RADIUS_BY_SUBTYPE = {
    "tactical_air_base": 5_000.0,  # 전술항공작전기지 (서울공항 등 공군 비행단)
    "air_defense_base": 500.0,  # 방공기지
    "explosive_firing_range": 1_000.0,  # 폭발물 관련 시설·사격장·훈련장
    "support_helicopter_base": 2_000.0,  # 지원·헬기전용작전기지
    "general": 300.0,  # 그 밖의 중요 군사기지·시설
}


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
class MilitaryRegulationTheme:
    """군사시설 1건에 중첩 적용되는 법적 근거(규정 테마) 1건.

    theme_id는 src.db/암호문 캐시의 (facility_id, regulation_theme) 복합키 중
    regulation_theme와 짝을 맞춘다. height_limit_enc만 z값 비공개 대상이다
    (CLAUDE.md 원칙 1·2).
    """

    theme_id: str
    label: str
    height_limit_enc: HeightLimitCiphertext = field(repr=False)


@dataclass
class MilitaryZone:
    """군사시설(보호구역/비행안전구역) 1건 — regulations에 담긴 테마마다 독립적으로 판정한다.

    facility_id는 src.db(구조화 기준값 DB)의 동일 facility_id 행과 대조하는 데 쓰인다.
    zone_subtype은 ZONE_RADIUS_BY_SUBTYPE 조회 키다. batch_height_limit_enc는 regulations의
    Z값들을 슬롯 여러 개짜리 CKKS 벡터 하나로 묶어 암호화해둔 것(SIMD 배치 데모 전용,
    slot 순서는 regulations 리스트 순서와 동일) — 아직 생성되지 않았으면 None이다.
    """

    facility_id: str
    name: str
    x_plain: float
    y_plain: float
    zone_subtype: str
    regulations: List[MilitaryRegulationTheme]
    batch_height_limit_enc: Optional[HeightLimitCiphertext] = field(default=None, repr=False)


def zone_radius_m(zone: MilitaryZone) -> float:
    """군사시설의 zone_subtype에 대응하는 인접 판정 반경(m) — 군사기지법 제5조 근거
    (ZONE_RADIUS_BY_SUBTYPE). 이 반경 수치 자체는 공개 법정 정보라 그대로 반환해도 된다."""
    return ZONE_RADIUS_BY_SUBTYPE.get(zone.zone_subtype, ADJACENCY_RADIUS_M)


# 문화재청 고시 남한산성 역사문화환경보존지역 — 성남시 수정구 방면 진입 지점(남한산성입구역
# 인근, 8호선)의 공개 좌표로 접지했다. 남한산성 자체는 광주시·하남시·성남시에 걸쳐 있다.
# TODO: 문화재보호법상 실제 고시 허용높이로 교체 예정 — 좌표는 실좌표 수준, 허용높이는 임의값.
HERITAGE_SITES: List[HeritageSite] = [
    HeritageSite(
        facility_id="heritage_namhansanseong",
        name="남한산성 역사문화환경보존지역 (성남 방면)",
        x_plain=127.1597,
        y_plain=37.4517,
        allowed_height_m=15.0,
    ),
]


def _load_military_regulation(
    facility_id: str, regulation_theme: str, label: str
) -> MilitaryRegulationTheme:
    """암호문 캐시(src.db.ciphertext_cache)에서 (facility_id, regulation_theme)의 높이제한
    암호문을 읽어온다.

    캐시가 비어 있으면(스크립트 미실행) 여기서 바로 실패시킨다 — 서비스가 평문 기본값
    등으로 조용히 대체하는 일이 없도록 하기 위함이다 (CLAUDE.md 절대 원칙 1).
    """
    row = load_ciphertext(facility_id, regulation_theme)
    if row is None:
        raise RuntimeError(
            f"'{facility_id}'/'{regulation_theme}'의 암호문 캐시가 없습니다. 먼저 "
            "`python scripts/generate_mock_ciphertexts.py`를 실행해 암호문 캐시를 준비하세요."
        )
    return MilitaryRegulationTheme(
        theme_id=regulation_theme,
        label=label,
        height_limit_enc=load_height_limit_ciphertext(row["ciphertext_blob"]),
    )


_BATCH_REGULATION_THEME = "__batch__"


def _load_military_batch_ciphertext(facility_id: str) -> Optional[HeightLimitCiphertext]:
    """CKKS SIMD 배치 데모용 — regulations의 여러 Z값을 슬롯 여러 개짜리 벡터 하나로 묶어
    암호화해둔 것을 조회한다. 아직 생성되지 않았으면(구버전 캐시) None을 반환해 배치 데모
    패널만 조용히 숨긴다 — 개별 테마 판정(원칙 1의 핵심 경로, _load_military_regulation)은
    이 함수와 무관하게 항상 정상 동작한다."""
    row = load_ciphertext(facility_id, _BATCH_REGULATION_THEME)
    if row is None:
        return None
    return load_height_limit_ciphertext(row["ciphertext_blob"])


# 성남 서울공항(성남비행장/K-16, 공군 제15특수임무비행단) — 경기도 성남시 수정구 심곡동
# 일대. 좌표는 항공정보간행물(AIP) 공개 기준점(ARP) 수준 근사치(위도 37-26N, 경도 127-07E)이며
# 활주로 등 정밀 시설 좌표가 아니다. 군사기지 및 군사시설 보호법상 제한보호구역(제9조)과
# 비행안전구역(제10조)이 중첩 지정되므로 규정 테마 2건을 함께 판정한다.
# TODO: 각 테마의 실제 고시 고도제한 수치로 교체 예정 — 고도제한 수치는 안보상 비공개이므로
# height_limit_m은 임의값(placeholder)을 유지한다 (좌표·시설 정체성만 실제 기준).
MILITARY_ZONES: List[MilitaryZone] = [
    MilitaryZone(
        facility_id="military_seongnam_airport",
        name="서울공항(성남비행장) 군사시설보호구역",
        x_plain=127.1167,
        y_plain=37.4333,
        zone_subtype="tactical_air_base",
        regulations=[
            _load_military_regulation(
                "military_seongnam_airport",
                "protect_zone",
                "군사기지 및 군사시설 보호법 제9조 (제한보호구역 고도제한)",
            ),
            _load_military_regulation(
                "military_seongnam_airport",
                "flight_safety",
                "군사기지 및 군사시설 보호법 제10조 (비행안전구역 기본표면)",
            ),
        ],
        batch_height_limit_enc=_load_military_batch_ciphertext("military_seongnam_airport"),
    ),
]
