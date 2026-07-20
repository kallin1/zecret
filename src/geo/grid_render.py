# 격자(grid) 단위 위험도 시각화 — 개별 건물 정밀 좌표/높이 대신 서버에서 렌더링된 격자 이미지만 반환 (체크포인트③)

from dataclasses import dataclass
from typing import List

from src.he.compare import HeightJudgment


@dataclass
class GridCell:
    """격자 셀 하나의 집계된 위험도 — 개별 건물 좌표/높이는 포함하지 않는다"""

    grid_x: int
    grid_y: int
    risk_level: str  # 예: "안전" / "주의" / "위험"


def aggregate_judgments_to_grid(
    judgments: List[HeightJudgment],
    grid_size_m: float,
) -> List[GridCell]:
    """개별 판정 결과들을 격자 단위로 집계 (정밀 좌표는 격자 인덱스로 뭉개짐)"""
    # TODO: judgments를 grid_size_m 간격의 격자로 집계하여 셀별 위험도 산출
    raise NotImplementedError


def render_grid_image(cells: List[GridCell]) -> bytes:
    """격자 위험도를 서버 사이드에서 이미지로 렌더링 (PNG 등 bytes 반환, 좌표/높이 원본 노출 없음)"""
    # TODO: matplotlib/PIL 등으로 격자 이미지 렌더링 후 bytes로 반환
    raise NotImplementedError
