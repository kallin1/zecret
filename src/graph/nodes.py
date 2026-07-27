# LangGraph 노드 구현 (CLAUDE.md 그래프 오케스트레이션 절 참고):
#   search_zone_node → (조건부 분기)
#     military      → he_compute_node → authority_verify_node → rag_check_node
#     그 외(비군사)  → plain_compute_node                       → rag_check_node
#   공통: rag_check_node → llm_summarize_node
#
# he_compute_node/authority_verify_node는 이번 단계에서 Mock이지만, 인터페이스는
# src.he.encryption의 실제 CKKS 교체 대상 함수와 그대로 맞춰져 있다.

import logging
from typing import Any, Dict, List

from dotenv import load_dotenv

from scripts.mock_authority_verify import verify_diff
from src.compliance import config
from src.compliance.geo_utils import haversine_m
from src.compliance.rules import evaluate_height_compliance
from src.db.queries import verify_height_against_db
from src.graph.llm_client import call_llm
from src.graph.state import ComplianceState
from src.he.encryption import compute_diff_ciphertext
from src.rag.qa import get_citations_for_facility

load_dotenv()
logger = logging.getLogger(__name__)

SUNLIGHT_SETBACK_FACILITY_ID = "sunlight_setback_general"
SUNLIGHT_SETBACK_FACILITY_NAME = "인접대지경계선 (일조권 사선제한)"


def search_zone_node(state: ComplianceState) -> Dict[str, Any]:
    """계획 위치 기준 ADJACENCY_RADIUS_M 반경 내 시설을 조회해 facility_type을 판별한다.

    군사시설을 최우선으로 확인하고(HE 경로 시연을 위해), 다음으로 국가유산을 확인한다.
    인접 시설이 없으면 항상 적용되는 일조권 사선제한으로 판정한다.
    """
    plan_x, plan_y = state["plan_x"], state["plan_y"]

    for zone in config.MILITARY_ZONES:
        if haversine_m(plan_x, plan_y, zone.x_plain, zone.y_plain) <= config.ADJACENCY_RADIUS_M:
            return {
                "facility_type": "military",
                "facility_id": zone.facility_id,
                "facility_name": zone.name,
            }

    for site in config.HERITAGE_SITES:
        if haversine_m(plan_x, plan_y, site.x_plain, site.y_plain) <= config.ADJACENCY_RADIUS_M:
            return {
                "facility_type": "heritage",
                "facility_id": site.facility_id,
                "facility_name": site.name,
            }

    return {
        "facility_type": "sunlight_setback",
        "facility_id": SUNLIGHT_SETBACK_FACILITY_ID,
        "facility_name": SUNLIGHT_SETBACK_FACILITY_NAME,
    }


def he_compute_node(state: ComplianceState) -> Dict[str, Any]:
    """군사시설 높이제한 기준값(암호문) - 계획높이(평문) 동형 뺄셈 (실제 TenSEAL CKKS 연산).

    diff는 여기서 복호화하지 않고 authority_verify_node로만 넘긴다.
    """
    zone = next(z for z in config.MILITARY_ZONES if z.facility_id == state["facility_id"])
    diff_ciphertext = compute_diff_ciphertext(zone.height_limit_enc, state["plan_height"])
    return {"diff_ciphertext": diff_ciphertext}


def authority_verify_node(state: ComplianceState) -> Dict[str, Any]:
    """관리기관 HSM 검증 API 자리 — scripts.mock_authority_verify.verify_diff()를 호출해
    diff 암호문(직렬화된 bytes)의 부호(초과 여부)만 확인한다. 실제 배포에서는 이 호출이
    관리기관 HSM API 엔드포인트 호출로 교체된다.

    margin은 군사시설 카테고리이므로 항상 None (CLAUDE.md 절대 원칙 1, 2).
    """
    exceeds = verify_diff(state["diff_ciphertext"].diff_enc)
    return {"computation_result": {"exceeds_limit": exceeds, "margin": None}}


def plain_compute_node(state: ComplianceState) -> Dict[str, Any]:
    """일조권 사선제한/국가유산 경관보호 — 평문 연산이므로 rules.evaluate_height_compliance를 그대로 호출."""
    facility_type = state["facility_type"]
    if facility_type == "heritage":
        site = next(s for s in config.HERITAGE_SITES if s.facility_id == state["facility_id"])
        reference_value: Any = site.allowed_height_m
    else:
        reference_value = state["setback_distance"]

    result = evaluate_height_compliance(facility_type, state["plan_height"], reference_value)
    return {"computation_result": result}


def rag_check_node(state: ComplianceState) -> Dict[str, Any]:
    """구조화 기준값 DB(src/db)와 facility_id 기반 정확 대조 (벡터 검색이 아님)."""
    verdict = verify_height_against_db(
        state["facility_id"], state["plan_height"], setback_distance_m=state.get("setback_distance")
    )
    verdict["matches_computation"] = verdict["exceeds_limit"] == state["computation_result"]["exceeds_limit"]
    return {"rag_verdict": verdict}


_LLM_SYSTEM_PROMPT = (
    "판정은 이미 끝났다. 너는 아래 판정 결과를 설명하는 문장만 만들어라. "
    "초과 여부를 스스로 재판단하거나 임의로 수치를 언급하지 마라. "
    "근거는 아래 조문 발췌에서만 인용한다."
)


def _status_label(exceeds_limit: bool) -> str:
    return "위반" if exceeds_limit else "적합"


def _fallback_message(facility_name: str, exceeds_limit: bool) -> str:
    """LLM 호출이 불가능하거나 실패했을 때 쓰는 결정론적 문구.

    이미 확정된 computation_result만 그대로 반영하므로, LLM 장애 시에도 판정 결과가
    왜곡되어 표시되는 일은 없다 (CLAUDE.md 절대 원칙 5).
    """
    return f"[{facility_name}] 판정 결과: {_status_label(exceeds_limit)}"


def _build_user_prompt(
    facility_name: str, exceeds_limit: bool, citations: List[Dict[str, Any]]
) -> str:
    """LLM에는 확정된 bool(exceeds_limit)과 근거 조문 텍스트만 넘긴다 — 계획 높이 원본값,
    정확한 좌표, margin 등은 이 프롬프트에 포함하지 않는다 (CLAUDE.md 절대 원칙 1, 5)."""
    citation_text = "\n".join(f"- {c['text']}" for c in citations) or "(관련 조문 근거 없음)"
    return (
        f"시설/기준: {facility_name}\n"
        f"판정 결과: {_status_label(exceeds_limit)}\n"
        f"근거 조문 발췌:\n{citation_text}\n\n"
        "위 판정 결과를 그대로 설명하는 한국어 문장을 1~2개로 작성하라."
    )


def llm_summarize_node(state: ComplianceState) -> Dict[str, Any]:
    """판정 결과(computation_result)와 RAG 근거 조문을 바탕으로 설명문을 생성한다.

    LLM은 판정을 다시 내리지 않는다 — exceeds_limit은 이미 확정된 입력으로만 주어지고,
    시스템 프롬프트가 재판단·임의 수치 언급을 명시적으로 금지한다 (CLAUDE.md 절대 원칙 5).
    call_llm()이 Claude/Gemini 중 설정된 쪽을 자동으로 고른다 — 둘 다 없거나 호출이
    실패하면 결정론적 템플릿으로 대체해, LLM 장애가 전체 파이프라인을 막지 않도록 한다.
    """
    exceeds_limit = state["computation_result"]["exceeds_limit"]
    facility_name = state["facility_name"]
    citations = get_citations_for_facility(state["facility_id"])

    try:
        final_message = call_llm(
            _LLM_SYSTEM_PROMPT, _build_user_prompt(facility_name, exceeds_limit, citations)
        )
    except Exception:
        logger.warning("llm_summarize_node: LLM 호출 실패, 폴백 문구로 대체", exc_info=True)
        final_message = _fallback_message(facility_name, exceeds_limit)

    return {"final_message": final_message, "rag_citations": citations}
