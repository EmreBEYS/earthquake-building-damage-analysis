from pathlib import Path

import geopandas as gpd
from shapely.geometry import Polygon

from earthquake_damage.sprint_00_14 import (
    PROJECT_ROOT,
    load_config,
    prepare_frames,
    validate_outputs,
    write_outputs,
)


def test_sprint_00_14_source_metrics_and_quality_counts() -> None:
    config = load_config()
    result = prepare_frames(
        PROJECT_ROOT / config["buildings_source"],
        PROJECT_ROOT / config["neighborhoods_source"],
        metric_crs=config["metric_crs"],
        thresholds=config["review_thresholds"],
    )

    assert result.buildings.crs.to_string() == "EPSG:32637"
    assert result.neighborhoods.crs.to_string() == "EPSG:32637"
    assert len(result.buildings) == 3_617
    assert len(result.neighborhoods) == 87
    assert (result.buildings["area_m2"] > 0).all()
    assert (result.buildings["perimeter_m"] > 0).all()
    assert result.neighborhoods["building_count"].sum() == 3_598
    assert result.report["checks"]["building_unmatched_count"] == 19
    assert result.report["checks"]["building_duplicate_geometry_rows"] == 2
    assert result.report["checks"]["building_overlap_pair_count"] == 8
    assert result.report["checks"]["building_partial_containment_count"] == 123
    assert result.report["checks"]["neighborhood_overlap_pair_count"] == 59
    assert result.report["checks"]["matched_neighborhood_count"] == 87
    assert result.report["semantics"]["building_level_official_label_transfer"] is False
    assert "official_total" not in result.neighborhoods.columns
    assert "severe_count" not in result.neighborhoods.columns


def test_deterministic_tie_break_prefers_larger_overlap(tmp_path: Path) -> None:
    buildings = gpd.GeoDataFrame(
        {
            "feature_id": ["b1"],
            "damage_grade": ["test"],
            "detection_method": ["test"],
            "source": ["test"],
        },
        geometry=[Polygon([(0, 0), (4, 0), (4, 2), (0, 2)])],
        crs="EPSG:32637",
    )
    neighborhoods = gpd.GeoDataFrame(
        {
            "neighborhood_id": ["n1", "n2"],
            "mahalle": ["one", "two"],
            "match_method": ["test", "test"],
        },
        geometry=[
            Polygon([(-1, -1), (3, -1), (3, 3), (-1, 3)]),
            Polygon([(3, -1), (5, -1), (5, 3), (3, 3)]),
        ],
        crs="EPSG:32637",
    )
    building_path = tmp_path / "buildings.geojson"
    neighborhood_path = tmp_path / "neighborhoods.geojson"
    buildings.to_file(building_path, driver="GeoJSON")
    neighborhoods.to_file(neighborhood_path, driver="GeoJSON")
    result = prepare_frames(
        building_path,
        neighborhood_path,
        metric_crs="EPSG:32637",
        thresholds={
            "building_area_min_m2": 1.0,
            "building_area_max_m2": 100_000.0,
            "full_containment_ratio": 0.999999,
        },
    )
    assert result.buildings.loc[0, "neighborhood_id"] == "n1"
    assert result.buildings.loc[0, "boundary_intersection_count"] == 2


def test_written_geopackage_and_geoparquet_reopen_and_validate(tmp_path: Path) -> None:
    config = load_config()
    result = prepare_frames(
        PROJECT_ROOT / config["buildings_source"],
        PROJECT_ROOT / config["neighborhoods_source"],
        metric_crs=config["metric_crs"],
        thresholds=config["review_thresholds"],
    )
    written = write_outputs(result, tmp_path)
    reopened = validate_outputs(
        output_directory=tmp_path,
        expected_buildings=3_617,
        expected_neighborhoods=87,
        crs="EPSG:32637",
    )
    assert written["gpkg"]["layers"]["buildings"]["invalid_geometry_count"] == 0
    assert reopened["geoparquet"]["layers"]["neighborhoods"]["feature_count"] == 87
