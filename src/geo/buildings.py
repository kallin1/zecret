# VWorld 건물통합정보(WFS) 배경 레이어 — 계획 건물 주변 실제 건물 footprint를 2.5D 압출로
# 보여주는 순수 시각화 배경 데이터다. 판정에는 전혀 관여하지 않는다 (CLAUDE.md: Streamlit
# 화면 코드와 HE/판정 로직 분리 — 이 모듈도 반대로 판정 로직을 전혀 갖지 않는다).
#
# 사전 조사 결과, VWorld의 3D 건물 데이터(Cesium 3D Tiles) 공개 API는 보안 규정으로 폐쇄되어
# 있어 이 앱에서는 쓸 수 없다. 대신 2D 건물통합정보(WFS, lt_c_bldginfo)에 높이/층수 속성이
# 함께 오는 것을 pydeck GeoJsonLayer로 압출(extrude)해 2.5D처럼 보이게 한다. 이 속성이
# 비어 있거나 0인 레코드가 많다는 것도 사전 조사로 확인되어 있어, 그런 레코드는 높이를
# 지어내지 않고 0(평면)으로 폴백한다 — 실제 층수·높이를 모르는 건물을 임의로 높게 그리면
# 안 되기 때문이다.
#
# VWorld 응답의 정확한 속성 필드명은 실제 발급받은 WFS 키로 응답을 받아봐야 확정할 수 있어,
# 아래 후보 필드명 목록은 최선 추정(best-effort)이며 실제 연동 시 재검증이 필요하다.

import os
from typing import Any, Dict, List

import requests

VWORLD_API_KEY = os.environ.get("VWORLD_API_KEY", "")

_WFS_URL = "https://api.vworld.kr/req/wfs"
_BUILDING_LAYER = "lt_c_bldginfo"
# bbox 반경(도 단위) 근사치 — 약 900m~1km 남짓. 배경 시각화 목적이라 정밀 미터 환산은
# 불필요하다.
_DEFAULT_HALF_EXTENT_DEG = 0.008

# 실제 응답 스키마 확정 전까지 시도해볼 높이/층수/이름 후보 필드명 (best-effort).
_HEIGHT_FIELD_CANDIDATES = ("heit", "bld_hg", "height")
_FLOOR_FIELD_CANDIDATES = ("gro_flo_co", "ground_floor_count")
_NAME_FIELD_CANDIDATES = ("bldnm", "buld_nm", "bld_nm")
_METERS_PER_FLOOR = 3.0


def fetch_nearby_building_footprints(
    center_x: float,
    center_y: float,
    half_extent_deg: float = _DEFAULT_HALF_EXTENT_DEG,
    timeout_s: float = 5.0,
) -> List[Dict[str, Any]]:
    """VWorld 건물통합정보 WFS에서 center 주변 bbox 안 건물 footprint(GeoJSON feature)를 가져온다.

    키 미설정·네트워크 실패·응답 파싱 실패 시 빈 리스트를 반환한다 — 배경 시각화 레이어일
    뿐이라, 실패해도 판정 화면(지도 외 나머지) 자체가 막히면 안 된다.
    """
    if not VWORLD_API_KEY:
        return []

    bbox = (
        f"{center_x - half_extent_deg},{center_y - half_extent_deg},"
        f"{center_x + half_extent_deg},{center_y + half_extent_deg}"
    )
    params = {
        "SERVICE": "WFS",
        "REQUEST": "GetFeature",
        "VERSION": "1.1.0",
        "TYPENAME": _BUILDING_LAYER,
        "BBOX": bbox,
        "SRSNAME": "EPSG:4326",
        "OUTPUT": "application/json",
        "MAXFEATURES": "300",
        "KEY": VWORLD_API_KEY,
    }
    try:
        response = requests.get(_WFS_URL, params=params, timeout=timeout_s)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    return payload.get("features", []) or []


def _first_present(props: Dict[str, Any], candidates) -> Any:
    for key in candidates:
        if key in props and props[key] not in (None, ""):
            return props[key]
    return None


def to_building_layer_data(features: List[Dict[str, Any]]) -> Dict[str, Any]:
    """GeoJSON feature 목록을 pydeck GeoJsonLayer(extruded=True, get_elevation=
    "properties.height_m")가 바로 쓸 수 있는 FeatureCollection으로 정리한다.

    height_m은 높이 속성이 있으면 그대로, 없고 층수만 있으면 층수*3m로 추정, 둘 다 없으면
    0(평면 폴백)이다 — 근거 없는 높이를 지어내지 않는다.
    """
    cleaned_features = []
    for feature in features:
        geometry = feature.get("geometry")
        if not geometry:
            continue
        props = feature.get("properties", {}) or {}

        height_m = _first_present(props, _HEIGHT_FIELD_CANDIDATES)
        if height_m is None:
            floor_count = _first_present(props, _FLOOR_FIELD_CANDIDATES)
            height_m = float(floor_count) * _METERS_PER_FLOOR if floor_count is not None else 0.0

        try:
            height_m = max(float(height_m), 0.0)
        except (TypeError, ValueError):
            height_m = 0.0

        cleaned_features.append(
            {
                "type": "Feature",
                "geometry": geometry,
                "properties": {"name": _first_present(props, _NAME_FIELD_CANDIDATES) or "", "height_m": height_m},
            }
        )
    return {"type": "FeatureCollection", "features": cleaned_features}
