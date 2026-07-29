# 구조화 기준값 DB — 일조권/문화재/군사시설 기준치를 (facility_id, regulation_theme)로
# 정확 대조하기 위한 SQLite 저장소 (RAG 벡터DB(src/rag)와는 별개이며, 벡터 검색이 아닌
# 정확한 키 조회 전용).
#
# 군사시설은 규정 테마 2건(제9조 제한보호구역 / 제10조 비행안전구역)이 중첩 적용되므로
# facility_id 단독이 아니라 (facility_id, regulation_theme) 복합키를 쓴다. 그 외
# 카테고리(문화재/일조권)는 규정 테마가 1개뿐이라 regulation_theme="default"로 둔다.
#
# 군사시설 행의 height_limit_m도 여기(서버 내부 DB)에는 평문으로 저장되지만, 이 값을
# 반환하는 함수(src.db.queries.verify_height_against_db)는 military 카테고리에 한해
# height_limit_m을 결과 dict에 절대 포함하지 않는다 (CLAUDE.md 절대 원칙 1, 2).

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "reference_facilities.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS height_limits (
    facility_id TEXT NOT NULL,
    regulation_theme TEXT NOT NULL,
    regulation_type TEXT NOT NULL,
    height_limit_m REAL NOT NULL,
    source_citation TEXT NOT NULL,
    effective_date TEXT NOT NULL,
    last_verified_date TEXT NOT NULL,
    PRIMARY KEY (facility_id, regulation_theme)
);
"""

# regulation_type: "military" | "heritage" | "sunlight_setback"
# regulation_theme: 군사시설만 "protect_zone"/"flight_safety"로 세분화, 그 외는 "default"
# height_limit_m: 군사시설/문화재는 임의값(placeholder), 일조권은 건축법 제61조의 공개된 임계값(9.0m)
_SAMPLE_ROWS = [
    (
        "military_seongnam_airport",
        "protect_zone",
        "military",
        45.0,
        "군사기지 및 군사시설 보호법 제9조 (서울공항 제한보호구역, 고도제한 수치 비공개)",
        "2020-01-01",
        "2026-01-01",
    ),
    (
        "military_seongnam_airport",
        "flight_safety",
        "military",
        60.0,
        "군사기지 및 군사시설 보호법 제10조 (서울공항 비행안전구역 기본표면, 표고 수치 비공개)",
        "2020-01-01",
        "2026-01-01",
    ),
    (
        "heritage_namhansanseong",
        "default",
        "heritage",
        15.0,
        "문화재보호법 제13조 (남한산성 역사문화환경보존지역 고시 허용높이)",
        "2019-06-01",
        "2026-01-01",
    ),
    (
        "sunlight_setback_general",
        "default",
        "sunlight_setback",
        9.0,
        "건축법 제61조, 시행령 제86조 (높이 9m 이하 → 1.5m 이상 이격 기준)",
        "2016-02-01",
        "2026-01-01",
    ),
]


def get_connection() -> sqlite3.Connection:
    """DB 커넥션을 열고 테이블이 없으면 생성한다. 호출부는 사용 후 반드시 close() 한다."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA_SQL)
    conn.commit()
    return conn


def seed_if_empty(conn: sqlite3.Connection) -> None:
    """테이블이 비어 있을 때만 샘플 기준값을 채운다 (idempotent)."""
    (count,) = conn.execute("SELECT COUNT(*) FROM height_limits").fetchone()
    if count == 0:
        conn.executemany(
            "INSERT INTO height_limits VALUES (?, ?, ?, ?, ?, ?, ?)",
            _SAMPLE_ROWS,
        )
        conn.commit()
