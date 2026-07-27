# 구조화 기준값 DB 조회 — facility_id 기반 정확 쿼리 (벡터 검색 아님).
# rag_check_node(src.graph.nodes)가 여기의 verify_height_against_db()만 호출한다.

from typing import Any, Dict, Optional

from src.compliance.config import SUNLIGHT_SETBACK_LOW_RISE_MIN_DISTANCE_M
from src.db.schema import get_connection, seed_if_empty


def _fetch_row(facility_id: str) -> Dict[str, Any]:
    """[내부 전용] facility_id 1건 조회.

    이 함수의 반환값(특히 military 행의 height_limit_m)을 그대로 외부에 노출하면 안
    된다 — verify_height_against_db() 안에서만 사용한다 (CLAUDE.md 절대 원칙 1).
    """
    conn = get_connection()
    try:
        seed_if_empty(conn)
        row = conn.execute(
            "SELECT * FROM height_limits WHERE facility_id = ?", (facility_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"unknown facility_id: {facility_id!r}")
    return dict(row)


def verify_height_against_db(
    facility_id: str,
    plan_height_plain: float,
    setback_distance_m: Optional[float] = None,
) -> Dict[str, Any]:
    """facility_id로 구조화 기준값 DB와 정확 대조해 초과 여부를 재확인한다.

    military/heritage는 height_limit_m을 단순 상한으로 쓰는 대조이지만, sunlight_setback은
    height_limit_m이 상한이 아니라 이격거리 요구치를 가르는 높이 임계값(9m)이므로, 여기서도
    src.compliance.rules와 동일한 공식을 독립적으로 재계산해 대조한다 — rules.py 결과와
    우연히 같은 코드 경로를 타지 않도록 하는 별도 검증(cross-check)이 목적이라 의도적으로
    로직을 중복시켰다.

    military 카테고리는 height_limit_m을 반환값에 포함하지 않는다 — 이 필드가 있으면
    Z값(높이제한 기준값)이 정밀 수치로 유추 가능해지기 때문이다 (CLAUDE.md 절대 원칙 1, 2).
    """
    row = _fetch_row(facility_id)
    regulation_type = row["regulation_type"]

    if regulation_type == "sunlight_setback":
        required_distance_m = (
            SUNLIGHT_SETBACK_LOW_RISE_MIN_DISTANCE_M
            if plan_height_plain <= row["height_limit_m"]
            else plan_height_plain / 2.0
        )
        exceeds = setback_distance_m < required_distance_m
    else:
        exceeds = plan_height_plain > row["height_limit_m"]

    verdict: Dict[str, Any] = {
        "facility_id": facility_id,
        "exceeds_limit": exceeds,
        "source_citation": row["source_citation"],
    }
    if regulation_type != "military":
        verdict["height_limit_m"] = row["height_limit_m"]
    return verdict
