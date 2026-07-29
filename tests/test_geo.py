# src/geo — 지도 시각화 보조 모듈(격자 위험도/건물 배경) 검증.
# 두 모듈 모두 판정에 관여하지 않는 순수 시각화 헬퍼라, 높이(Z)를 다루지 않는다.

from src.compliance.search import NearbyFacility
from src.geo.buildings import fetch_nearby_building_footprints, to_building_layer_data
from src.geo.risk_grid import build_risk_grid


def test_risk_grid_cell_near_facility_has_higher_count():
    facility = NearbyFacility(
        facility_type="military",
        facility_id="military_seongnam_airport",
        facility_name="서울공항(성남비행장) 군사시설보호구역",
        distance_m=100.0,
        x_plain=127.1167,
        y_plain=37.4333,
    )
    cells = build_risk_grid(
        center_x=127.1167, center_y=37.4333, radius_m=500.0, facilities=[facility], cell_size_m=250.0
    )
    assert cells
    assert any(cell.facility_count >= 1 for cell in cells)
    assert all(cell.facility_count in (0, 1) for cell in cells)


def test_risk_grid_empty_when_no_facilities():
    cells = build_risk_grid(center_x=130.0, center_y=35.0, radius_m=500.0, facilities=[], cell_size_m=250.0)
    assert cells
    assert all(cell.facility_count == 0 for cell in cells)


def test_risk_grid_handles_zero_radius():
    assert build_risk_grid(center_x=127.0, center_y=37.0, radius_m=0.0, facilities=[]) == []


def test_fetch_building_footprints_returns_empty_without_api_key(monkeypatch):
    monkeypatch.setattr("src.geo.buildings.VWORLD_API_KEY", "")
    assert fetch_nearby_building_footprints(127.1167, 37.4333) == []


def test_to_building_layer_data_falls_back_to_flat_when_no_height_attrs():
    features = [{"geometry": {"type": "Point", "coordinates": [127.0, 37.0]}, "properties": {}}]
    collection = to_building_layer_data(features)
    assert collection["type"] == "FeatureCollection"
    assert collection["features"] == [
        {"type": "Feature", "geometry": features[0]["geometry"], "properties": {"name": "", "height_m": 0.0}}
    ]


def test_to_building_layer_data_estimates_height_from_floor_count():
    features = [
        {
            "geometry": {"type": "Point", "coordinates": [127.0, 37.0]},
            "properties": {"gro_flo_co": "5", "bldnm": "테스트빌딩"},
        }
    ]
    collection = to_building_layer_data(features)
    assert collection["features"][0]["properties"]["height_m"] == 15.0
    assert collection["features"][0]["properties"]["name"] == "테스트빌딩"


def test_to_building_layer_data_skips_features_without_geometry():
    features = [{"properties": {}}]
    assert to_building_layer_data(features) == {"type": "FeatureCollection", "features": []}
