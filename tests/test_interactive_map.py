from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import box

from earthquake_damage.interactive_map import (
    DEFAULT_LAYERS,
    LAYER_LABELS,
    PERIOD_LAYERS,
    available_layers,
    count_points_within,
    detail_rows,
    focus_view,
    reconstruction_status,
    selected_points,
    spectral_cover,
)

ROOT = Path(__file__).resolve().parents[1]
CRS = "EPSG:32637"


def test_count_points_within_counts_each_footprint_once():
    polygons = gpd.GeoDataFrame(geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)], crs=CRS)
    footprints = gpd.GeoDataFrame(
        geometry=[box(1, 1, 2, 2), box(3, 3, 4, 4), box(12, 1, 13, 2), box(50, 50, 51, 51)],
        crs=CRS,
    )
    assert count_points_within(polygons, footprints).tolist() == [2, 1]
    assert count_points_within(polygons, footprints.iloc[:0]).tolist() == [0, 0]


def test_reconstruction_status_thresholds():
    status = reconstruction_status(np.array([0, 4, 4, 4]), np.array([0, 0, 1, 2]))
    assert status.tolist() == ["no_osm_footprint", "none_removed", "some_removed",
                               "mostly_removed"]


def test_spectral_cover_is_area_share():
    buildings = gpd.GeoDataFrame(geometry=[box(0, 0, 10, 10), box(20, 0, 30, 10)], crs=CRS)
    spectral = gpd.GeoDataFrame(geometry=[box(5, 0, 15, 10)], crs=CRS)
    assert spectral_cover(buildings, spectral).tolist() == pytest.approx([0.5, 0.0])
    assert spectral_cover(buildings, spectral.iloc[:0]).tolist() == [0.0, 0.0]


def test_focus_view_centres_and_clamps_zoom():
    center, zoom = focus_view((38.2, 38.3, 38.4, 38.4))
    assert center == pytest.approx({"lat": 38.35, "lon": 38.3})
    assert 10 <= zoom <= 17.5
    assert focus_view((38.0, 38.0, 38.0, 38.0))[1] == 17.5


def test_period_layers_are_labelled_and_defaults_available():
    for period, layers in PERIOD_LAYERS.items():
        assert set(layers) <= set(LAYER_LABELS)
        assert set(DEFAULT_LAYERS[period]) <= set(available_layers(period))


def test_detail_rows_translate_and_format():
    rows = dict(detail_rows({
        "feature_id": "X1", "district": "Battalgazi", "mahalle": "Saray Mahallesi",
        "damage_grade": "Destroyed", "predicted_damage": "damaged", "confidence": 0.55,
        "low_confidence": True, "area_m2": 12345.0, "perimeter_m": 400.0,
        "spectral_cover_2022_2023": 0.25, "osm_buildings_2023": 8, "removed_by_2026": 5,
        "new_by_2026": 1, "reconstruction_status": "mostly_removed",
    }))
    assert rows["EMSR648 hasar sınıfı"] == "Yıkılmış"
    assert rows["Model tahmini"] == "Hasarlı"
    assert rows["Model güveni"] == "0,55 · düşük güven"
    assert rows["Poligon alanı"] == "12.345 m²"
    assert rows["Spektral değişim 2022→2023"] == "%25"
    assert rows["2026'ya kadar kaldırılan / yeni"] == "5 / 1"
    assert "çoğu kaldırılmış" in rows["2023→2026 durumu"]


def test_detail_rows_handle_missing_snapshot_counts():
    rows = dict(detail_rows({"osm_buildings_2023": -1, "removed_by_2026": 0, "new_by_2026": 0,
                             "reconstruction_status": "snapshot_unavailable",
                             "spectral_cover_2022_2023": float("nan")}))
    assert rows["2023 OSM binası (içinde)"] == "—"
    assert rows["Spektral değişim 2022→2023"] == "—"


def test_selected_points_tolerates_missing_events():
    assert selected_points(None) == []
    assert selected_points({"selection": {"points": [{"customdata": "A"}]}}) == [
        {"customdata": "A"}
    ]


def test_committed_building_details_are_complete():
    table = pd.read_csv(ROOT / "data/dashboard/sprint_00-22/building_details.csv")
    assert len(table) == 3617 and table["feature_id"].is_unique
    probabilities = table.filter(like="probability_").sum(axis=1)
    assert probabilities.to_numpy() == pytest.approx(np.ones(len(table)), abs=1e-3)
    # Removed candidates are a subset of the 2023 footprints, so never outnumber them.
    known = table[table["osm_buildings_2023"] >= 0]
    assert (known["removed_by_2026"] <= known["osm_buildings_2023"]).all()
