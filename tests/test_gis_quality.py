"""Sprint 00-24 — GIS quality and cross-sprint consistency checks on committed outputs.

These tests read only files that are in the repository, so they run the same on a clean
clone, in CI, on Windows and on macOS.
"""

import hashlib
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "data/dashboard"
# Generous envelope around Battalgazi + Yeşilyurt (lon/lat).
MALATYA_ENVELOPE = (38.0, 38.15, 38.6, 38.55)
METRIC = "EPSG:32637"

COMMITTED_LAYERS = sorted(
    path for path in DASHBOARD.rglob("*.geojson") if path.stat().st_size > 0
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def neighborhoods():
    return gpd.read_file(DASHBOARD / "sprint_00-12/aoi05_neighborhoods.geojson")


@pytest.mark.parametrize("path", COMMITTED_LAYERS, ids=lambda p: p.relative_to(DASHBOARD).as_posix())
def test_layer_is_wgs84_valid_and_inside_malatya(path):
    layer = gpd.read_file(path)
    assert len(layer) > 0
    assert layer.crs is not None and layer.crs.to_epsg() == 4326
    geometry = layer.geometry
    assert not geometry.isna().any() and not geometry.is_empty.any()
    assert geometry.is_valid.all(), f"{int((~geometry.is_valid).sum())} invalid geometries"
    west, south, east, north = layer.total_bounds
    env_w, env_s, env_e, env_n = MALATYA_ENVELOPE
    assert env_w <= west and east <= env_e and env_s <= south and north <= env_n


def test_neighbourhood_identity_is_consistent_across_sprints(neighborhoods):
    names = set(neighborhoods["mahalle"])
    ids = set(neighborhoods["neighborhood_id"])
    assert len(names) == len(ids) == 87
    official = pd.read_csv(DASHBOARD / "sprint_00-15/official_neighborhood_statistics.csv")
    assert set(official["neighborhood_id"]) == ids
    comparison = pd.read_csv(DASHBOARD / "sprint_00-20/neighborhood_comparison.csv")
    assert set(comparison["neighborhood_id"]) == ids and set(comparison["mahalle"]) == names
    districts = pd.read_csv(DASHBOARD / "sprint_00-21/neighborhood_districts.csv")
    assert set(districts["neighborhood_id"]) == ids
    recon = pd.read_csv(DASHBOARD / "sprint_00-19/neighborhood_reconstruction_indicators.csv")
    assert set(recon["neighborhood"]) - {"unknown"} == names


def test_neighbourhood_topology_has_no_material_overlaps(neighborhoods):
    metric = neighborhoods.to_crs(METRIC).reset_index(drop=True)
    pairs = gpd.sjoin(metric, metric, predicate="intersects")
    pairs = pairs[pairs.index < pairs["index_right"]]
    worst = 0.0
    for left, right in zip(pairs.index, pairs["index_right"], strict=True):
        a, b = metric.geometry.iloc[left], metric.geometry.iloc[right]
        worst = max(worst, a.intersection(b).area / min(a.area, b.area))
    assert worst < 0.01, f"largest overlap is {worst:.2%} of the smaller neighbourhood"


def test_metric_areas_agree_with_the_comparison_table(neighborhoods):
    areas = neighborhoods.to_crs(METRIC).set_index("mahalle").geometry.area / 1e6
    comparison = pd.read_csv(DASHBOARD / "sprint_00-20/neighborhood_comparison.csv")
    stored = comparison.set_index("mahalle")["area_km2"]
    assert np.allclose(stored.loc[areas.index], areas, rtol=1e-3)
    assert 150 < areas.sum() < 260


def test_official_record_total_is_conserved_everywhere():
    total = 46563
    official = pd.read_csv(DASHBOARD / "sprint_00-15/official_neighborhood_statistics.csv")
    assert official["official_total"].sum() == total
    classes = ["no_damage", "slight_damage", "moderate_damage", "heavy_damage",
               "urgent_demolition", "destroyed"]
    assert (official[classes].sum(axis=1) == official["official_total"]).all()
    comparison = pd.read_csv(DASHBOARD / "sprint_00-20/neighborhood_comparison.csv")
    assert comparison["official_records"].sum() == total
    severe = official[["heavy_damage", "urgent_demolition", "destroyed"]].sum(axis=1)
    assert (severe == official["severe_count"]).all()


def test_emsr648_predictions_and_details_share_identifiers():
    emsr = gpd.read_file(DASHBOARD / "sprint_00-12/copernicus_damage_polygons.geojson")
    predictions = gpd.read_file(DASHBOARD / "sprint_00-17/predicted_damage.geojson")
    details = pd.read_csv(DASHBOARD / "sprint_00-22/building_details.csv")
    ids = set(emsr["feature_id"])
    assert len(ids) == len(emsr) == 3617
    assert set(predictions["feature_id"]) == ids == set(details["feature_id"])
    assert set(emsr["damage_grade"]) <= {"No visible damage", "Possibly damaged", "Damaged",
                                         "Destroyed"}
    probabilities = predictions.filter(like="probability_").sum(axis=1)
    assert np.allclose(probabilities, 1, atol=1e-6)
    assert ((predictions["confidence"] < 0.6) == predictions["low_confidence"]).all()


def test_change_outputs_never_carry_damage_fields():
    from earthquake_damage.reconstruction_change_analysis import assert_no_damage_fields

    for name in ("reconstruction_change_map.geojson",
                 "neighborhood_reconstruction_indicators.csv"):
        path = DASHBOARD / "sprint_00-19" / name
        columns = (gpd.read_file(path, rows=1) if path.suffix == ".geojson"
                   else pd.read_csv(path, nrows=1)).columns
        assert_no_damage_fields(columns)


@pytest.mark.parametrize(("report", "key", "folder"), [
    ("reports/sprint_00-19/reconstruction_validation.json", "outputs_sha256", "sprint_00-19"),
    ("reports/sprint_00-20/spatial_analysis_validation.json", "outputs_sha256", "sprint_00-20"),
])
def test_validation_report_checksums_match_committed_outputs(report, key, folder):
    recorded = json.loads((ROOT / report).read_text(encoding="utf-8"))[key]
    for name, digest in recorded.items():
        assert _sha256(DASHBOARD / folder / name) == digest, name


def test_manifest_checksums_match_committed_outputs():
    manifest = json.loads((DASHBOARD / "sprint_00-17/manifest.json").read_text(encoding="utf-8"))
    assert _sha256(ROOT / manifest["output"]["path"]) == manifest["output"]["sha256"]
    details = json.loads(
        (DASHBOARD / "sprint_00-22/building_details.source.json").read_text(encoding="utf-8"))
    assert _sha256(DASHBOARD / "sprint_00-22/building_details.csv") == details["sha256"]


def test_hotspot_columns_are_internally_consistent():
    table = pd.read_csv(DASHBOARD / "sprint_00-20/neighborhood_comparison.csv")
    config = json.loads((ROOT / "configs/sprint_00_20.json").read_text(encoding="utf-8"))
    for variable in config["hotspot_variables"]:
        z, p = table[f"{variable}__gi_z"], table[f"{variable}__gi_p"]
        hot = table[f"{variable}__hotspot"]
        assert ((hot.str.startswith("hot")) <= (z > 0)).all()
        assert ((hot.str.startswith("cold")) <= (z < 0)).all()
        assert (hot[p >= 0.10] == "not_significant").all()
        # An FDR discovery is always significant on its own as well.
        assert (p[table[f"{variable}__gi_fdr"]] < 0.05).all()
