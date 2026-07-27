# [Phase 7 벤치마크] Mock(평문) 파이프라인과 실제 TenSEAL CKKS 파이프라인의 연산 시간을
# 비교 측정한다.
#
# 측정 포인트:
#   1. he_compute_node 내부 순수 연산 시간 — LangGraph .invoke()를 거치지 않고 노드
#      함수를 직접 호출해 상태 전이 오버헤드가 섞이지 않게 한다.
#   2. plain_compute_node(평문, 동일 스키마/입력 기준)와의 속도 비교.
#   3. authority_verify 단계에서 개별 verify_diff() N회 호출 vs verify_diff_batch()
#      1회 호출의 라운드트립 절감 효과.
#
# 결과는 콘솔에 출력하고 docs/benchmark_phase7.json에도 저장한다 (README 표 갱신용).
#
# 사용법: python scripts/benchmark_he.py

import json
import os
import statistics
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.mock_authority_verify import verify_diff, verify_diff_batch  # noqa: E402
from src.compliance.config import HERITAGE_SITES, MILITARY_ZONES  # noqa: E402
from src.graph.nodes import he_compute_node, plain_compute_node  # noqa: E402

N_TRIALS = 30
BATCH_SIZE = 20
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "benchmark_phase7.json")


def _time_calls(fn, n=N_TRIALS):
    times = []
    for _ in range(n):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return times


def _summary(times_sec):
    ms = [t * 1000 for t in times_sec]
    return {
        "n": len(ms),
        "mean_ms": round(statistics.mean(ms), 4),
        "median_ms": round(statistics.median(ms), 4),
        "stdev_ms": round(statistics.stdev(ms), 4) if len(ms) > 1 else 0.0,
        "min_ms": round(min(ms), 4),
        "max_ms": round(max(ms), 4),
    }


def benchmark_he_compute_node():
    """he_compute_node 내부(동형 뺄셈) 순수 연산 시간 — 노드 함수를 직접 호출한다.

    공개 컨텍스트는 프로세스당 최초 1회만 디스크에서 읽어 캐시되므로(src/he/context.py),
    그 최초 로드 비용(cold start)이 측정을 왜곡하지 않도록 워밍업 후 steady-state만
    측정한다. cold start 비용은 별도로 함께 보고한다.
    """
    zone = MILITARY_ZONES[0]
    state = {"facility_id": zone.facility_id, "plan_height": 50.0}

    cold_start_start = time.perf_counter()
    he_compute_node(state)  # 공개 컨텍스트 최초 로드 포함
    cold_start_sec = time.perf_counter() - cold_start_start

    return _time_calls(lambda: he_compute_node(state)), cold_start_sec


def benchmark_plain_compute_node():
    """plain_compute_node(평문 연산) 순수 연산 시간 — 동일하게 노드 함수를 직접 호출한다."""
    site = HERITAGE_SITES[0]
    state = {"facility_type": "heritage", "facility_id": site.facility_id, "plan_height": 10.0}
    return _time_calls(lambda: plain_compute_node(state))


def benchmark_authority_verify_batching(n_repeats=10):
    """authority_verify 단계 — 개별 verify_diff() N회 대 verify_diff_batch() 1회 비교.

    비밀 컨텍스트 최초 로드(디스크 읽기+역직렬화, 1회성 워밍업 비용)가 어느 쪽이
    먼저 측정되느냐에 따라 결과를 왜곡할 수 있어, 측정 전에 verify_diff()를 한 번
    호출해 워밍업한다 (이 워밍업 없이 측정했을 때 배치 쪽이 부당하게 빨라 보이는
    현상을 실제로 확인했다 — 콜드스타트 아티팩트였을 뿐 배치 자체의 효과가 아니었다).

    단발성 측정은 실행할 때마다 -44% ~ +27%로 들쭉날쭉해(노이즈 수준) 결론을 낼 수
    없었다 — n_repeats회 반복해 총합으로 판단한다.
    """
    zone = MILITARY_ZONES[0]
    diff_ciphertext = he_compute_node({"facility_id": zone.facility_id, "plan_height": 50.0})[
        "diff_ciphertext"
    ]
    diff_blobs = [diff_ciphertext.diff_enc] * BATCH_SIZE

    verify_diff(diff_blobs[0])  # 워밍업 — 비밀 컨텍스트를 미리 로드해 캐시해 둔다

    individual_total_sec = 0.0
    batch_total_sec = 0.0
    for _ in range(n_repeats):
        start = time.perf_counter()
        for blob in diff_blobs:
            verify_diff(blob)
        individual_total_sec += time.perf_counter() - start

        start = time.perf_counter()
        verify_diff_batch(diff_blobs)
        batch_total_sec += time.perf_counter() - start

    return individual_total_sec, batch_total_sec


def main():
    he_times, he_cold_start_sec = benchmark_he_compute_node()
    plain_times = benchmark_plain_compute_node()
    individual_total_sec, batch_total_sec = benchmark_authority_verify_batching()

    he_summary = _summary(he_times)
    plain_summary = _summary(plain_times)
    speed_ratio = he_summary["mean_ms"] / plain_summary["mean_ms"]
    batch_savings_pct = (1 - batch_total_sec / individual_total_sec) * 100

    result = {
        "phase": 7,
        "he_compute_node": he_summary,
        "he_compute_node_cold_start_ms": round(he_cold_start_sec * 1000, 4),
        "plain_compute_node": plain_summary,
        "he_vs_plain_speed_ratio": round(speed_ratio, 1),
        "authority_verify_batching": {
            "batch_size": BATCH_SIZE,
            "note": (
                "이 Mock 환경은 같은 프로세스 안에서 함수 호출로 관리기관 검증을 흉내내므로 "
                "실제 네트워크 왕복(RTT)이 없다 — 그래서 배치 처리 자체의 시간 절감은 미미하거나 "
                "없다(워밍업 전에는 측정 순서에 따라 배치가 부당하게 빨라 보이는 콜드스타트 "
                "아티팩트가 있었음을 실제로 확인, 워밍업 후에는 유의미한 차이가 없었다). 실제 "
                "배포에서 authority_verify가 진짜 HSM API 호출로 교체되면, N번의 개별 요청을 "
                "1번의 배치 요청으로 묶는 것 자체가 N번의 네트워크 RTT를 1번으로 줄이는 효과를 "
                "낸다 — 그 절감은 여기서는 측정할 수 없고 RTT가 존재하는 실 환경에서만 나타난다."
            ),
            "individual_calls_total_ms": round(individual_total_sec * 1000, 4),
            "single_batch_call_total_ms": round(batch_total_sec * 1000, 4),
            "in_process_savings_pct": round(batch_savings_pct, 1),
        },
    }

    print(f"he_compute_node        : mean={he_summary['mean_ms']}ms  median={he_summary['median_ms']}ms  (n={he_summary['n']}, steady-state)")
    print(f"he_compute_node (cold) : {result['he_compute_node_cold_start_ms']}ms (공개 컨텍스트 최초 로드 포함, 1회성)")
    print(f"plain_compute_node     : mean={plain_summary['mean_ms']}ms  median={plain_summary['median_ms']}ms  (n={plain_summary['n']})")
    print(f"HE / plain speed ratio : {speed_ratio:.1f}x (steady-state 기준)")
    print(
        f"authority_verify batching (batch_size={BATCH_SIZE}, 워밍업 후 측정): "
        f"individual={result['authority_verify_batching']['individual_calls_total_ms']}ms total, "
        f"batch={result['authority_verify_batching']['single_batch_call_total_ms']}ms total, "
        f"in-process savings={batch_savings_pct:.1f}% (실제 RTT 절감 효과는 아님 — 위 note 참고)"
    )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\nbenchmark written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
