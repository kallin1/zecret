# 암호문 캐시 — 원본 Z값(군사시설 높이제한 기준값)은 절대 저장하지 않고, ciphertext_blob
# (opaque bytes)과 he_context_version/issued_at/expires_at/facility_id만 보관한다
# (CLAUDE.md 데이터 저장소 설계: "암호문 캐시"). src.db.schema의 height_limits 테이블
# (구조화 기준값 DB, 정확값 대조용으로 평문을 내부에 보관)과는 완전히 별개의 저장소다.
#
# scripts/generate_mock_ciphertexts.py(관리기관 역할의 오프라인 스크립트)만 이 테이블에
# 기록(store_ciphertext)하고, 서비스(src.compliance.config)는 조회(load_ciphertext)만
# 한다 — 이 모듈은 비밀키를 전혀 다루지 않는다.

import sqlite3
from pathlib import Path
from typing import Optional

DB_PATH = Path(__file__).parent / "ciphertext_cache.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ciphertext_cache (
    facility_id TEXT PRIMARY KEY,
    ciphertext_blob BLOB NOT NULL,
    he_context_version TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    """DB 커넥션을 열고 테이블이 없으면 생성한다. 호출부는 사용 후 반드시 close() 한다."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA_SQL)
    conn.commit()
    return conn


def store_ciphertext(
    facility_id: str,
    ciphertext_blob: bytes,
    he_context_version: str,
    issued_at: str,
    expires_at: str,
) -> None:
    """[생성 스크립트 전용] facility_id의 암호문 캐시 행을 upsert한다.

    ciphertext_blob 외에는 opaque 메타데이터만 받는다 — 평문 높이제한값은 이 함수의
    파라미터에 애초에 존재하지 않는다.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO ciphertext_cache (facility_id, ciphertext_blob, he_context_version, issued_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(facility_id) DO UPDATE SET
                ciphertext_blob = excluded.ciphertext_blob,
                he_context_version = excluded.he_context_version,
                issued_at = excluded.issued_at,
                expires_at = excluded.expires_at
            """,
            (facility_id, ciphertext_blob, he_context_version, issued_at, expires_at),
        )
        conn.commit()
    finally:
        conn.close()


def load_ciphertext(facility_id: str) -> Optional[sqlite3.Row]:
    """서비스가 facility_id로 암호문 캐시 행(ciphertext_blob 포함)을 조회한다.

    이 테이블에는 애초에 평문 필드가 없으므로, 이 함수의 반환값을 그대로 로그/응답에
    남겨도 원본 Z값이 노출될 수 없다.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM ciphertext_cache WHERE facility_id = ?", (facility_id,)
        ).fetchone()
    finally:
        conn.close()
    return row
