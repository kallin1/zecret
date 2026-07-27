# Phase 6 완료 기준 검증 — Mock에서 실제 TenSEAL CKKS 연산으로 교체한 뒤에도:
#   1) Phase 5 baseline(docs/baseline_phase5.json)과 동일한 bool 결과가 나온다.
#   2) app.py/LangGraph 노드 어디에도 원본 z값이 평문으로 노출되지 않는다.
#   3) scripts/keys/(비밀키)가 서비스 코드(src.he.encryption, src.graph.nodes,
#      src.compliance.rules/config)에서 import되지 않는다.

import ast
import json
from pathlib import Path

from src.compliance.config import MILITARY_ZONES
from src.graph.runner import run_full_compliance_check
from src.he.encryption import HeightLimitCiphertext, compute_diff_ciphertext
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
    """config.MILITARY_ZONES의 암호문 필드에는 bytes만 있고 평문 float 필드가 없다."""
    zone = MILITARY_ZONES[0]
    assert isinstance(zone.height_limit_enc, HeightLimitCiphertext)
    assert isinstance(zone.height_limit_enc.ciphertext_enc, bytes)
    field_names = {f for f in vars(zone.height_limit_enc)}
    assert field_names == {"ciphertext_enc"}


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
