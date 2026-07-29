# Phase 5(RAG+LLM 연결) 시점의 전체 파이프라인 출력을 Phase 6 비교용 baseline으로 저장한다.
#
# CLOVASTUDIO_API_KEY가 설정되어 있지 않으면 llm_summarize_node는 폴백 템플릿 문구로
# 동작한다 — 이 baseline은 그 상태(폴백 모드)를 있는 그대로 기록한 것이다. 이후 실제
# CLOVASTUDIO_API_KEY를 넣고 다시 캡처하면 final_message가 LLM이 생성한 문장으로 바뀐
# baseline을 새로 남길 수 있다.
#
# 사용법: python scripts/capture_phase5_baseline.py

import json
import os
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.graph.runner import run_full_compliance_check  # noqa: E402

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "baseline_phase5.json")

SCENARIOS = [
    {
        "label": "military+heritage+sunlight_setback (성남 서울공항 보호구역·남한산성 중첩 위치)",
        "plan_x_plain": 127.1567,
        "plan_y_plain": 37.4504,
        "plan_height_plain": 20.0,
        "setback_distance_m": 3.0,
    },
    {
        "label": "military 두 테마 모두 위반 (계획높이 65m > 45m·60m 기준)",
        "plan_x_plain": 127.1567,
        "plan_y_plain": 37.4504,
        "plan_height_plain": 65.0,
        "setback_distance_m": 3.0,
    },
    {
        "label": "sunlight_setback only (인접 시설 반경 밖)",
        "plan_x_plain": 130.0,
        "plan_y_plain": 35.0,
        "plan_height_plain": 8.0,
        "setback_distance_m": 1.0,
    },
]


def main() -> None:
    llm_mode = "live" if os.environ.get("CLOVASTUDIO_API_KEY") else "fallback (CLOVASTUDIO_API_KEY 미설정)"
    baseline = {"phase": 5, "llm_mode": llm_mode, "scenarios": []}

    for scenario in SCENARIOS:
        params = {k: v for k, v in scenario.items() if k != "label"}
        results = run_full_compliance_check(**params)
        baseline["scenarios"].append(
            {
                "label": scenario["label"],
                "input": params,
                "results": [asdict(r) for r in results],
            }
        )

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)

    print(f"baseline written to {OUTPUT_PATH} (llm_mode={llm_mode})")


if __name__ == "__main__":
    main()
