# 반복 질의 기반 임계값 오라클 방어 — "Z값 자체는 절대 복호화하지 않는다"는 CLAUDE.md
# 절대 원칙 1을 지키더라도, authority_verify_node가 매번 정확한 bool(초과 여부)을
# 돌려주는 한 계획높이(plan_height)를 바꿔가며 반복 질의하면 이진탐색으로 Z값을 원하는
# 정밀도까지 역산할 수 있다 — 이는 암호 스킴이 아니라 "비교 결과 1비트를 반복 공개하는
# 질의 인터페이스" 자체의 근본적 한계다 (Dinur–Nissim reconstruction theorem, Differential
# Privacy의 Sparse Vector Technique이 다루는 것과 동일한 문제 형태). 자세한 배경/근거는
# docs/oracle_defense.md 참고.
#
# 여기서는 노이즈를 섞어 답을 흐리는 방식(DP 스타일)을 택하지 않는다 — 이 서비스의 판정은
# "위반/적합"이라는 법적 판단이라, 확률적으로 틀린 답을 섞는 것은 정확성 원칙(CLAUDE.md
# 절대 원칙 1)과 정면으로 충돌한다. 대신 (facility_id, regulation_theme) 조합별로 누적
# 질의 횟수에 하드 캡을 걸고, 캡을 넘으면 판정 자체를 거부한다 — 실제 관리기관 HSM이라면
# 이 지점에서 이상 질의 패턴을 로깅/감사하는 것과 같은 역할이다.
#
# 이 카운터는 요청자(신원)를 구분하지 않고 (facility_id, regulation_theme) 단위로만
# 누적된다 — 보호 대상이 "이 시설의 비공개 Z값 그 자체"이지 "이 사람이 몇 번 물어봤는지"가
# 아니기 때문이다(신원 기반 세분화는 실 서비스 전환 시 확장 대상, docs/oracle_defense.md
# 참고). 프로세스 재시작 시 초기화되는 인메모리 카운터라는 것도 PoC 단계의 한계다 — 실제
# 배포에서는 관리기관 HSM 쪽에 영속 저장소로 옮겨야 한다.

import os
from typing import Dict, Tuple

from dotenv import load_dotenv

# 이 모듈은 nodes.py -> runner.py -> app.py로 이어지는 import 체인에서 가장 먼저 로드되는
# 축에 속해, app.py/nodes.py 자신의 load_dotenv() 호출보다 먼저 DEFAULT_QUERY_BUDGET이
# 계산돼버려 .env의 HE_QUERY_BUDGET_PER_REGULATION이 반영되지 않는 문제가 있었다. 다른
# 모듈처럼 이 파일 자신도 방어적으로 load_dotenv()를 호출해 순서와 무관하게 만든다.
load_dotenv()

DEFAULT_QUERY_BUDGET = int(os.getenv("HE_QUERY_BUDGET_PER_REGULATION", "50"))

_query_counts: Dict[Tuple[str, str], int] = {}


class QueryBudgetExceededError(RuntimeError):
    """(facility_id, regulation_theme) 조합의 누적 질의 횟수가 예산을 넘었을 때 발생.

    exceeds_limit을 임의로 True/False 중 하나로 지어내지 않고 예외를 던져 호출부가
    "판정 거부"임을 명확히 구분하게 한다 — 잘못된 값을 침묵 속에 반환하는 것보다,
    막혔다는 사실 자체를 드러내는 편이 원칙 1의 정신에 맞다.
    """

    def __init__(self, facility_id: str, regulation_theme: str, budget: int, query_count: int):
        self.facility_id = facility_id
        self.regulation_theme = regulation_theme
        self.budget = budget
        self.query_count = query_count  # 이 예외를 유발한 시점의 누적 질의 횟수 (Langfuse span에 그대로 실림)
        super().__init__(
            f"'{facility_id}'/'{regulation_theme}' 조합에 대한 조회 한도({budget}회)를 "
            "초과했습니다. 반복 질의를 통한 비공개 높이제한값(Z) 역산을 막기 위한 조치이며, "
            "이 시설·규정에 대한 추가 확인은 관리기관에 직접 문의해야 합니다."
        )


def consume_query_budget(
    facility_id: str, regulation_theme: str, *, budget: int = DEFAULT_QUERY_BUDGET
) -> int:
    """(facility_id, regulation_theme) 질의 카운트를 1 늘리고 남은 예산을 확인한다.

    반환값은 이번 호출까지 누적된 질의 횟수다. 예산을 넘기면 카운트를 늘린 채로
    QueryBudgetExceededError를 던진다 — 이후 재시도도 계속 거부되어야 하기 때문이다.
    """
    key = (facility_id, regulation_theme)
    count = _query_counts.get(key, 0) + 1
    _query_counts[key] = count
    if count > budget:
        raise QueryBudgetExceededError(facility_id, regulation_theme, budget, count)
    return count


def get_query_count(facility_id: str, regulation_theme: str) -> int:
    """현재까지 누적된 질의 횟수를 조회만 한다 (증가시키지 않음) — 테스트/모니터링용."""
    return _query_counts.get((facility_id, regulation_theme), 0)


def reset_query_budget() -> None:
    """모든 (facility_id, regulation_theme) 카운터를 초기화한다 — 테스트 간 격리 전용.

    실제 배포에서는 이런 리셋 없이 영속 저장소에 누적되어야 하므로, 이 함수는 프로덕션
    경로(src/graph, app.py)에서는 호출하지 않는다.
    """
    _query_counts.clear()
