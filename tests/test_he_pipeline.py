# Phase 6 완료 기준 검증 — Mock에서 실제 TenSEAL CKKS 연산으로 교체한 뒤에도:
#   1) Phase 5 baseline(docs/baseline_phase5.json)과 동일한 bool 결과가 나온다.
#   2) app.py/LangGraph 노드 어디에도 원본 z값이 평문으로 노출되지 않는다.
#   3) scripts/keys/(비밀키)가 서비스 코드(src.he.encryption, src.graph.nodes,
#      src.compliance.rules/config)에서 import되지 않는다.

import ast
import json
from pathlib import Path

from src.compliance.config import MILITARY_ZONES
from src.graph.runner import compute_he_batch_demo, run_full_compliance_check
from src.he.encryption import HeightLimitCiphertext, compute_diff_ciphertext
from src.tokens import is_valid_token, parse_token
from tests.he_test_helpers import encrypt_for_test

BASELINE_PATH = Path(__file__).parent.parent / "docs" / "baseline_phase5.json"


def _load_baseline_military_results():
    with open(BASELINE_PATH, encoding="utf-8") as f:
        baseline = json.load(f)
    military_by_input = {}
    for scenario in baseline["scenarios"]:
        for item in scenario["results"]:
            if item["facility_type"] == "military":
                key = (
                    scenario["input"]["plan_x_plain"],
                    scenario["input"]["plan_y_plain"],
                    scenario["input"]["plan_height_plain"],
                )
                military_by_input[key] = item["exceeds_limit"]
    return military_by_input


def test_he_result_matches_phase5_baseline():
    """Phase 5(Mock HE) baseline과 Phase 6(실제 TenSEAL CKKS) 결과의 exceeds_limit이 같아야 한다."""
    baseline_military = _load_baseline_military_results()
    assert baseline_military, "baseline_phase5.json에 military 시나리오가 있어야 이 테스트가 의미가 있다"

    for (plan_x, plan_y, plan_height), expected_exceeds in baseline_military.items():
        results = run_full_compliance_check(plan_x, plan_y, plan_height, setback_distance_m=3.0)
        military_items = [r for r in results if r.facility_type == "military"]
        assert military_items, f"입력 {(plan_x, plan_y, plan_height)}에 military 항목이 없다"
        for item in military_items:
            assert item.exceeds_limit == expected_exceeds, (
                f"plan_height={plan_height}: HE 결과={item.exceeds_limit}, "
                f"Phase 5 baseline={expected_exceeds} — HE 연산 자체를 점검해야 한다"
            )
            assert item.margin is None


def test_compute_diff_ciphertext_matches_authority_verify():
    """he_compute_node/authority_verify_node가 쓰는 것과 동일한 함수 조합이 올바른 bool을 낸다."""
    reference_value = encrypt_for_test(45.0)
    from scripts.mock_authority_verify import verify_diff

    for plan_height, expected in [(30.0, False), (44.0, False), (46.0, True), (60.0, True)]:
        diff = compute_diff_ciphertext(reference_value, plan_height)
        assert verify_diff(diff.diff_enc) is expected


def test_diff_ciphertext_is_opaque_bytes_not_plaintext():
    """diff_enc는 직렬화된 bytes일 뿐, 어디에도 계획높이/기준값 차이가 평문 숫자로 담기지 않는다."""
    reference_value = encrypt_for_test(45.0)
    diff = compute_diff_ciphertext(reference_value, 30.0)  # 실제 diff는 15.0
    assert isinstance(diff.diff_enc, bytes)
    # 평문 차이값(15.0)이 바이트 시퀀스 안에 텍스트로 등장하지 않는지 확인
    assert b"15.0" not in diff.diff_enc


def test_military_zone_ciphertext_holds_only_bytes():
    """config.MILITARY_ZONES의 규정 테마마다 암호문 필드에는 bytes만 있고 평문 float 필드가 없다."""
    zone = MILITARY_ZONES[0]
    assert len(zone.regulations) >= 2  # 제9조 보호구역 + 제10조 비행안전구역, 최소 2개 테마
    for regulation in zone.regulations:
        assert isinstance(regulation.height_limit_enc, HeightLimitCiphertext)
        assert isinstance(regulation.height_limit_enc.ciphertext_enc, bytes)
        field_names = {f for f in vars(regulation.height_limit_enc)}
        assert field_names == {"ciphertext_enc"}


# --- CKKS SIMD 배치 데모 (요청: "z암호화 연산을 더 강하게 보여줄 방법") ---
# 규정 테마 여러 개의 Z값을 슬롯 1개짜리 벡터 여러 개로 나누지 않고, 슬롯 N개짜리 벡터
# 하나로 묶어 동형 뺄셈 1회 + HSM 복호화 1회로 전부 판정한다. 공식 판정 경로
# (run_full_compliance_check, 테마별 개별 he_compute+authority_verify)와는 완전히
# 별개의 데모 전용 경로라, 결과가 서로 일치하는지가 이 테스트의 핵심이다.


def test_batch_demo_matches_individual_theme_results():
    """배치 연산(슬롯 N개짜리 벡터 1개) 결과가 개별 판정(테마별 벡터 각각)과 정확히 일치해야 한다."""
    zone = MILITARY_ZONES[0]
    for plan_height in [30.0, 45.0 + 1e-6, 50.0, 65.0]:
        individual_results = {
            regulation.theme_id: run_full_compliance_check(
                zone.x_plain, zone.y_plain, plan_height, setback_distance_m=3.0
            )
            for regulation in zone.regulations
        }
        batch_demo = compute_he_batch_demo(zone, plan_height)
        assert batch_demo is not None
        for regulation in zone.regulations:
            individual_item = next(
                item
                for item in individual_results[regulation.theme_id]
                if item.facility_type == "military" and item.regulation_theme == regulation.theme_id
            )
            assert batch_demo.exceeds_limit_by_theme[regulation.theme_id] == individual_item.exceeds_limit


def test_batch_demo_token_preview_exposes_no_ciphertext_bytes():
    """token_preview는 참조 토큰만 담아야 한다 (CLAUDE.md 절대 원칙 2, 체크포인트 ④).

    과거엔 ciphertext_blob의 hex 프리뷰/바이트 길이를 그대로 화면에 노출했었다 — 이 테스트는
    그 필드들이 다시 부활하지 않는지, 그리고 클라이언트가 받는 값이 원본을 재구성할 수 없는
    "HE:{facility_id}:{regulation_theme}" 형식의 토큰뿐인지 확인한다.
    """
    zone = MILITARY_ZONES[0]
    batch_demo = compute_he_batch_demo(zone, 50.0)
    assert batch_demo.token_preview is not None
    assert set(batch_demo.token_preview.keys()) == {"token", "he_context_version"}
    token = batch_demo.token_preview["token"]
    assert is_valid_token(token)
    dataset_id, reference_id = parse_token(token)
    assert dataset_id == zone.facility_id
    assert reference_id == "__batch__"


def test_batch_demo_returns_none_without_batch_ciphertext():
    """배치 암호문이 없는(테마 1개뿐이거나 캐시 미생성) 시설은 조용히 None을 반환한다."""
    from dataclasses import replace

    single_theme_zone = replace(MILITARY_ZONES[0], regulations=MILITARY_ZONES[0].regulations[:1])
    assert compute_he_batch_demo(single_theme_zone, 50.0) is None


def _collect_imported_names(module_path: Path):
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name)
    return names


def test_service_code_never_imports_secret_key_module():
    """서비스 코드(src/)는 scripts.keys나 비밀 컨텍스트 파일 경로를 직접 참조하지 않는다.

    scripts.mock_authority_verify(함수 호출 경계)는 import해도 되지만, 그 안의
    SECRET_CONTEXT_PATH/비밀 컨텍스트 로딩 로직 자체를 src/가 흉내내면 안 된다.
    """
    src_dir = Path(__file__).parent.parent / "src"
    for py_file in src_dir.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        assert "authority_secret_context" not in source, f"{py_file}가 비밀 컨텍스트 파일명을 직접 참조한다"
        assert "scripts.keys" not in source, f"{py_file}가 scripts.keys를 직접 참조한다"
        assert "save_secret_key" not in source, f"{py_file}가 비밀키 직렬화를 직접 수행한다"
