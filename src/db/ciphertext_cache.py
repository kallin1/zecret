# 암호문 캐시 — 원본 Z값(군사시설 높이제한 기준값)은 절대 저장하지 않고, ciphertext_blob
# (opaque bytes)과 he_context_version/issued_at/expires_at/facility_id/regulation_theme만
# 보관한다 (CLAUDE.md 데이터 저장소 설계: "암호문 캐시"). src.db.schema의 height_limits
# 테이블(구조화 기준값 DB, 정확값 대조용으로 평문을 내부에 보관)과는 완전히 별개의 저장소다.
#
# 군사시설 1건에 여러 규정 테마(예: 보호구역/비행안전구역)가 중첩 적용될 수 있어, PK를
# facility_id 단독이 아니라 (facility_id, regulation_theme) 복합키로 둔다.
#
# scripts/generate_mock_ciphertexts.py(관리기관 역할의 오프라인 스크립트)만 이 테이블에
# 기록(store_ciphertext)하고, 서비스(src.compliance.config)는 조회(load_ciphertext)만
# 한다 — 이 모듈은 비밀키를 전혀 다루지 않는다.

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

DB_PATH = Path(__file__).parent / "ciphertext_cache.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS ciphertext_cache (
    facility_id TEXT NOT NULL,
    regulation_theme TEXT NOT NULL,
    ciphertext_blob BLOB NOT NULL,
    he_context_version TEXT NOT NULL,
    issued_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (facility_id, regulation_theme)
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
    regulation_theme: str,
    ciphertext_blob: bytes,
    he_context_version: str,
    issued_at: str,
    expires_at: str,
) -> None:
    """[생성 스크립트 전용] (facility_id, regulation_theme)의 암호문 캐시 행을 upsert한다.

    ciphertext_blob 외에는 opaque 메타데이터만 받는다 — 평문 높이제한값은 이 함수의
    파라미터에 애초에 존재하지 않는다.
    """
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO ciphertext_cache
                (facility_id, regulation_theme, ciphertext_blob, he_context_version, issued_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(facility_id, regulation_theme) DO UPDATE SET
                ciphertext_blob = excluded.ciphertext_blob,
                he_context_version = excluded.he_context_version,
                issued_at = excluded.issued_at,
                expires_at = excluded.expires_at
            """,
            (facility_id, regulation_theme, ciphertext_blob, he_context_version, issued_at, expires_at),
        )
        conn.commit()
    finally:
        conn.close()


def load_ciphertext(facility_id: str, regulation_theme: str) -> Optional[sqlite3.Row]:
    """서비스가 (facility_id, regulation_theme)로 암호문 캐시 행(ciphertext_blob 포함)을 조회한다.

    이 테이블에는 애초에 평문 필드가 없으므로, 이 함수의 반환값을 그대로 로그/응답에
    남겨도 원본 Z값이 노출될 수 없다.
    """
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM ciphertext_cache WHERE facility_id = ? AND regulation_theme = ?",
            (facility_id, regulation_theme),
        ).fetchone()
    finally:
        conn.close()
    return row


def describe_ciphertext_for_display(facility_id: str, regulation_theme: str) -> Optional[Dict[str, Any]]:
    """[표시 전용] 화면에서 "이게 진짜 암호문이다"를 보여주기 위한 순수 프레젠테이션 데이터.

    ciphertext_blob을 hex로 일부만 잘라 보여주고 전체 바이트 길이를 담을 뿐, 복호화하거나
    평문을 유추할 수 있는 어떤 연산도 하지 않는다 — 이 함수가 반환하는 값은 원본 Z값과
    수학적으로 무관한 opaque 데이터의 겉모습(hex 문자열, 길이)뿐이다.
    """
    row = load_ciphertext(facility_id, regulation_theme)
    if row is None:
        return None
    blob: bytes = row["ciphertext_blob"]
    return {
        "hex_preview": blob[:48].hex(),
        "byte_length": len(blob),
        "he_context_version": row["he_context_version"],
    }
