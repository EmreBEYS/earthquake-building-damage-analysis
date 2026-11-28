import json
import math

import numpy as np
import pytest
from shapely.geometry import box

from earthquake_damage.spatial_analysis import (
    benjamini_hochberg,
    contiguity_neighbors,
    getis_ord_gi_star,
    global_morans_i,
    grid_cells,
    grid_queen_neighbors,
    hotspot_class,
    lisa_class,
    local_morans_i,
    run,
    subset_neighbors,
)

LINE = [np.array([1]), np.array([0, 2]), np.array([1, 3]), np.array([2])]


def test_queen_contiguity_counts_corner_touches():
    squares = [box(0, 0, 1, 1), box(1, 0, 2, 1), box(0, 1, 1, 2), box(1, 1, 2, 2)]
    neighbors = contiguity_neighbors(squares)
    assert [len(n) for n in neighbors] == [3, 3, 3, 3]


def test_contiguity_tolerance_bridges_digitising_gaps():
    gap = [box(0, 0, 1, 1), box(1.5, 0, 2.5, 1)]
    assert [len(n) for n in contiguity_neighbors(gap)] == [0, 0]
    assert [len(n) for n in contiguity_neighbors(gap, tolerance=0.3)] == [1, 1]


def test_global_morans_i_matches_hand_calculation():
    # z = [-1.5, -0.5, 0.5, 1.5]; lags = [-0.5, -0.5, 0.5, 0.5] → I = 4/4 · 2 / 5 = 0.4
    result = global_morans_i([1, 2, 3, 4], LINE, permutations=99, seed=1)
    assert result["I"] == pytest.approx(0.4)
    assert result["expected_I"] == pytest.approx(-1 / 3)


def test_global_morans_i_detects_clustering():
    rows, cols = np.divmod(np.arange(36), 6)
    neighbors = grid_queen_neighbors(rows, cols)
    clustered = (cols >= 3).astype(float)
    result = global_morans_i(clustered, neighbors, permutations=199, seed=3)
    assert result["I"] > 0.5
    assert result["p_sim"] <= 0.01


def test_gi_star_matches_hand_calculation():
    # Unit 3: members {2, 3}, Σx = 7, x̄ = 2.5, S = √1.25, √((4·2 − 4)/3) = √(4/3)
    result = getis_ord_gi_star([1, 2, 3, 4], LINE)
    expected = (7 - 2.5 * 2) / (math.sqrt(1.25) * math.sqrt(4 / 3))
    assert result["z"][3] == pytest.approx(expected)
    assert result["z"][0] == pytest.approx(-expected)


def test_gi_star_marks_islands_and_constant_values_as_missing():
    result = getis_ord_gi_star([1, 2, 3], [np.array([1]), np.array([0]), np.array([], int)])
    assert np.isnan(result["z"][2])
    assert np.isnan(getis_ord_gi_star([5, 5, 5, 5], LINE)["z"]).all()


def test_local_moran_quadrants_and_significance():
    rows, cols = np.divmod(np.arange(36), 6)
    neighbors = grid_queen_neighbors(rows, cols)
    values = (cols >= 3).astype(float)
    result = local_morans_i(values, neighbors, permutations=199, seed=5)
    interior_high = 3 * 6 + 5  # row 3, col 5: high value among high neighbours
    interior_low = 3 * 6 + 0
    assert result["quadrant"][interior_high] == "HH"
    assert result["quadrant"][interior_low] == "LL"
    assert result["p_sim"][interior_high] < 0.05


def test_benjamini_hochberg_step_up():
    flags = benjamini_hochberg([0.01, 0.02, 0.03, 0.5, np.nan], alpha=0.05)
    assert flags.tolist() == [True, True, True, False, False]


def test_hotspot_and_lisa_classes():
    assert hotspot_class(2.8, 0.005) == "hot_99"
    assert hotspot_class(-2.1, 0.04) == "cold_95"
    assert hotspot_class(1.7, 0.08) == "hot_90"
    assert hotspot_class(0.5, 0.6) == "not_significant"
    assert hotspot_class(float("nan"), float("nan")) == "no_data"
    assert lisa_class("HH", 0.01) == "HH"
    assert lisa_class("LH", 0.2) == "not_significant"


def test_subset_neighbors_reindexes():
    kept = subset_neighbors(LINE, np.array([True, False, True, True]))
    assert [n.tolist() for n in kept] == [[], [2], [1]]


def test_grid_cells_cover_bounds():
    cells = grid_cells((0, 0, 1000, 600), 500)
    assert len(cells) == 4
    assert {(r, c) for r, c, _ in cells} == {(0, 0), (0, 1), (1, 0), (1, 1)}


# ---------------------------------------------------------------------------
# End-to-end on a synthetic 3×3 neighbourhood mosaic
# ---------------------------------------------------------------------------


def _write_geojson(path, frame):
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_crs(4326).to_file(path, driver="GeoJSON")


def test_run_end_to_end(tmp_path):
    import geopandas as gpd
    import pandas as pd

    crs = "EPSG:32637"
    origin_x, origin_y = 500000, 4240000
    names, polygons = [], []
    for row in range(3):
        for col in range(3):
            names.append(f"M{row}{col}")
            polygons.append(box(origin_x + col * 1000, origin_y + row * 1000,
                                origin_x + (col + 1) * 1000, origin_y + (row + 1) * 1000))
    hoods = gpd.GeoDataFrame(
        {"neighborhood_id": [f"relation/{i}" for i in range(9)], "mahalle": names,
         "aoi_coverage_ratio": [1.0] * 9, "coverage_group": ["high"] * 9},
        geometry=polygons, crs=crs,
    )
    _write_geojson(tmp_path / "hoods.geojson", hoods)

    severe = [300, 280, 40, 260, 250, 30, 20, 25, 10]
    pd.DataFrame({
        "neighborhood_id": hoods["neighborhood_id"], "mahalle": names,
        "official_total": [400] * 9, "severe_count": severe,
        "severe_ratio": [s / 400 for s in severe],
        "no_damage": [100] * 9, "slight_damage": [0] * 9, "moderate_damage": [0] * 9,
        "heavy_damage": severe, "urgent_demolition": [0] * 9, "destroyed": [0] * 9,
    }).to_csv(tmp_path / "official.csv", index=False)

    footprints, grades = [], []
    for index, polygon in enumerate(polygons):
        x0, y0 = polygon.bounds[:2]
        for k in range(6):
            footprints.append(box(x0 + 100 + k * 120, y0 + 400, x0 + 180 + k * 120, y0 + 480))
            grades.append("Destroyed" if k < severe[index] // 60 else "No visible damage")
    copernicus = gpd.GeoDataFrame(
        {"feature_id": [f"B{i}" for i in range(len(grades))], "damage_grade": grades},
        geometry=footprints, crs=crs,
    )
    _write_geojson(tmp_path / "copernicus.geojson", copernicus)
    predictions = copernicus.rename(columns={"damage_grade": "observed_damage"})
    predictions["predicted_damage"] = np.where(
        predictions["observed_damage"] == "Destroyed", "destroyed", "no_visible_damage"
    )
    predictions["low_confidence"] = False
    _write_geojson(tmp_path / "predicted.geojson", predictions)
    spectral = gpd.GeoDataFrame({"change_id": ["c0"]},
                                geometry=[polygons[0].buffer(-300)], crs=crs)
    _write_geojson(tmp_path / "spectral.geojson", spectral)

    pd.DataFrame({
        "neighborhood": names + ["unknown"],
        "osm_buildings_2023": [100] * 9 + [1], "osm_buildings_2026": [90] * 9 + [1],
        "footprint_area_2023_m2": [50000.0] * 9 + [10.0],
        "footprint_area_2026_m2": [45000.0] * 9 + [10.0],
        "net_footprint_area_change_pct": [-10.0] * 9 + [0.0],
        "removed_candidates": [s // 20 for s in severe] + [0],
        "removed_share_of_2023_pct": [s / 20 for s in severe] + [0.0],
        "new_candidates": [1] * 9 + [0], "new_footprint_density_per_km2": [1.0] * 9 + [0.0],
        "renewal_turnover_pct": [5.0] * 9 + [0.0],
        "spectral_change_share_pct": [10.0] * 9 + [0.0],
    }).to_csv(tmp_path / "recon.csv", index=False)
    recon_map = gpd.GeoDataFrame(
        {"reconstruction_class": ["removed_candidate"] * 3},
        geometry=[footprints[0], footprints[1], footprints[6]], crs=crs,
    )
    recon_map.to_parquet(tmp_path / "recon.parquet")

    config = json.loads(
        (__import__("pathlib").Path(__file__).resolve().parents[1]
         / "configs/sprint_00_20.json").read_text(encoding="utf-8")
    )
    config.update({
        "neighborhoods": "hoods.geojson", "official_statistics": "official.csv",
        "copernicus": "copernicus.geojson", "predictions": "predicted.geojson",
        "spectral_change_2022_2023": "spectral.geojson", "reconstruction_indicators": "recon.csv",
        "reconstruction_map": "recon.parquet", "osm_post_event_snapshot": "missing.geojson",
        "output_directory": "out", "report_directory": "reports", "permutations": 99,
    })
    report = run(tmp_path, config)

    assert report["neighborhoods"] == 9
    assert report["weights"]["islands"] == 0
    table = pd.read_csv(tmp_path / "out/neighborhood_comparison.csv")
    assert table["official_records"].sum() == 3600
    assert table["emsr_buildings"].sum() == len(grades)
    top_left = table.set_index("mahalle").loc["M00"]
    assert top_left["official_severe_per_km2"] == pytest.approx(300)
    assert top_left["emsr_severe_share"] == pytest.approx(5 / 6, abs=1e-4)  # CSV keeps 4 decimals
    assert top_left["spectral_change_2022_2023_pct"] == pytest.approx(16.0)
    assert top_left["rank_official_severe_ratio"] == 1
    moran = {row["variable"]: row for row in report["global_morans_i"]}
    assert moran["official_severe_ratio"]["morans_i"] > 0
    layer = gpd.read_file(tmp_path / "out/neighborhood_spatial_analysis.geojson")
    assert "official_severe_ratio__hotspot_tr" in layer.columns
    assert report["grid"]["osm_post_event_snapshot_sha256"] is None
    assert (tmp_path / "reports/spatial_analysis_validation.json").exists()
