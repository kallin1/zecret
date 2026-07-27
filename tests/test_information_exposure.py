# 군사시설(비행안전구역) 카테고리는 z값(높이제한 기준값) 비공개 대상이라, 판정 결과에
# 정밀 수치가 전혀 담기지 않아야 한다 (CLAUDE.md 절대 원칙 1, 2). 반대로 일조권/국가유산
# 카테고리는 margin(정밀 수치)이 그대로 담겨 있어야 한다 — 이 대비를 확인하는 것이 목적이다.

from dataclasses import asdict

from src.compliance.config import MILITARY_ZONES
from src.compliance.report import build_compliance_report
from src.compliance.rules import evaluate_height_compliance
from tests.he_test_helpers import encrypt_for_test


def test_military_result_never_carries_margin():
    """군사시설 판정 결과에는 어떤 plan_height/기준값 조합에서도 margin이 없다.

    plan_height가 기준값과 완전히 같은 극단 케이스(45.0)는 CKKS 근사 연산의 본질적
    한계로 부호가 불안정해 의도적으로 제외했다 (tests/test_compliance_rules.py 참고).
    """
    reference_value = encrypt_for_test(45.0)
    for plan_height in [0.1, 44.9, 45.1, 200.0]:
        result = evaluate_height_compliance("military", plan_height, reference_value)
        assert result["margin"] is None


def test_report_military_items_expose_only_boolean():
    """build_compliance_report()가 만든 군사시설 항목은 exceeds_limit(bool)만 정보를 담고,
    margin은 항상 None이다 — 정밀 좌표차·높이차를 유추할 수치가 반환값에 없어야 한다.
    """
    zone = MILITARY_ZONES[0]
    report = build_compliance_report(
        plan_x_plain=zone.x_plain,
        plan_y_plain=zone.y_plain,
        plan_height_plain=100.0,
        setback_distance_m=3.0,
    )
    military_items = [item for item in report if item.facility_type == "military"]
    assert military_items, "인접 반경 내 군사시설이 최소 1건은 있어야 이 테스트가 의미가 있다"

    for item in military_items:
        as_dict = asdict(item)
        assert as_dict["margin"] is None
        assert isinstance(as_dict["exceeds_limit"], bool)


def test_report_heritage_and_setback_items_expose_margin():
    """대조군: 일조권/국가유산 카테고리는 margin(정밀 수치)이 그대로 노출되어야 한다
    (군사시설과 달리 이 두 카테고리는 z값 비공개 대상이 아니기 때문)."""
    report = build_compliance_report(
        plan_x_plain=127.123456,
        plan_y_plain=37.124123,
        plan_height_plain=10.0,
        setback_distance_m=3.0,
    )
    non_military_items = [item for item in report if item.facility_type != "military"]
    assert non_military_items

    for item in non_military_items:
        assert item.margin is not None
        assert isinstance(item.margin, float)
