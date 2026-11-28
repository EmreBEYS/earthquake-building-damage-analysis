"""Sprint 00-19 reconstruction change analysis tests (no network)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from earthquake_damage.reconstruction_change_analysis import (
    OSM_TO_RECONSTRUCTION,
    assert_no_damage_fields,
    bare_soil_index,
    change_signal_count,
    classify_footprint,
    direction_hint,
    merge_overpass_payloads,
    neighborhood_indicators,
    overpass_query,
    overpass_to_geojson,
    reflectance,
    tile_bounds,
)

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------- unit


def test_reflectance_applies_offset_and_masks_nodata():
    result = reflectance(np.array([0, 1000, 3500], dtype="uint16"), 0.0001, -0.1)
    assert np.isnan(result[0])
    assert result[1] == pytest.approx(0.0, abs=1e-6)
    assert result[2] == pytest.approx(0.25, abs=1e-6)


def test_offset_changes_ndvi_so_it_must_not_be_ignored():
    red_dn, nir_dn = np.array([2500.0]), np.array([3000.0])
    raw = (nir_dn - red_dn) / (nir_dn + red_dn)
    red, nir = reflectance(red_dn, 1e-4, -0.1), reflectance(nir_dn, 1e-4, -0.1)
    corrected = (nir - red) / (nir + red)
    assert corrected[0] == pytest.approx(0.05 / 0.35, rel=1e-4)
    assert abs(corrected[0] - raw[0]) > 0.05


def test_bare_soil_index_formula():
    value = bare_soil_index(
        np.array([0.10]), np.array([0.15]), np.array([0.20]), np.array([0.25])
    )
    assert value[0] == pytest.approx((0.40 - 0.30) / 0.70, rel=1e-5)


def test_change_signal_count_uses_absolute_thresholds_and_ignores_nan():
    deltas = {
        "ndvi": np.array([0.3, -0.3, 0.0, np.nan]),
        "ndbi": np.array([-0.2, 0.0, 0.0, 0.5]),
        "bsi": np.array([0.2, 0.0, 0.0, np.nan]),
    }
    thresholds = {"absolute_delta_ndvi": 0.2, "absolute_delta_ndbi": 0.15,
                  "absolute_delta_bsi": 0.15}
    assert change_signal_count(deltas, thresholds).tolist() == [3, 1, 0, 1]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((0.5, -0.1, 0.1), "vegetation_increase"),
        ((-0.1, 0.3, 0.0), "built_index_increase"),
        ((0.0, 0.1, -0.4), "bare_soil_index_decrease"),
        ((np.nan, 0.1, 0.1), "insufficient_data"),
    ],
)
def test_direction_hint_is_descriptive(values, expected):
    assert direction_hint(*values) == expected


def test_classify_footprint_maps_status_and_evidence_without_relabelling():
    assert classify_footprint("unmatched", 10, 6, 0.5) == ("removed_candidate", "osm_and_spectral", 0.6)
    assert classify_footprint("newly_mapped", 10, 2, 0.5) == ("new_candidate", "osm_only", 0.2)
    assert classify_footprint("unchanged", 0, 0, 0.5) == (
        "persistent", "osm_only_no_clear_pixels", None)
    # Strong spectral change never turns a persistent footprint into a removal.
    assert classify_footprint("unchanged", 4, 4, 0.5)[0] == "persistent"
    with pytest.raises(ValueError):
        classify_footprint("demolished", 1, 1, 0.5)
    with pytest.raises(ValueError):
        classify_footprint("unmatched", 1, 1, 0)


def test_every_osm_status_has_a_reconstruction_class():
    from earthquake_damage.building_change_analysis import STATUSES

    assert set(STATUSES) == set(OSM_TO_RECONSTRUCTION)


def test_damage_fields_are_rejected_from_change_outputs():
    assert_no_damage_fields(["unit_id", "reconstruction_class", "evidence"])
    for column in ("damage_grade", "hasar_sinifi", "EMSR648_overlap", "severity"):
        with pytest.raises(ValueError, match="damage fields"):
            assert_no_damage_fields(["unit_id", column])


def test_overpass_query_orders_bbox_south_west_north_east():
    query = overpass_query((38.2, 38.28, 38.36, 38.39), "2023-02-24T00:00:00Z")
    assert '[date:"2023-02-24T00:00:00Z"]' in query
    assert "(38.280000,38.200000,38.390000,38.360000)" in query


def test_overpass_to_geojson_keeps_closed_ways_and_dates_them():
    ring = [{"lon": 0, "lat": 0}, {"lon": 1, "lat": 0}, {"lon": 1, "lat": 1},
            {"lon": 0, "lat": 0}]
    payload = {
        "osm3s": {"timestamp_osm_base": "2026-07-28T02:16:18Z"},
        "elements": [
            {"type": "way", "id": 1, "geometry": ring, "tags": {"building": "yes"},
             "version": 3, "timestamp": "2022-01-01T00:00:00Z"},
            {"type": "way", "id": 2, "geometry": ring[:3]},
            {"type": "node", "id": 3},
        ],
    }
    document = overpass_to_geojson(payload, "2023-02-24T00:00:00Z")
    assert [f["id"] for f in document["features"]] == ["way/1"]
    properties = document["features"][0]["properties"]
    assert properties["@snapshotTimestamp"] == "2023-02-24T00:00:00Z"
    assert properties["@lastEdit"] == "2022-01-01T00:00:00Z"
    assert document["metadata"]["open_ways_dropped"] == 1


def test_tile_bounds_cover_the_box_without_gaps():
    tiles = tile_bounds((0.0, 10.0, 4.0, 12.0), 2)
    assert len(tiles) == 4
    assert tiles[0] == (0.0, 10.0, 2.0, 11.0)
    assert tiles[-1] == (2.0, 11.0, 4.0, 12.0)
    assert sum((e - w) * (n - s) for w, s, e, n in tiles) == pytest.approx(8.0)
    with pytest.raises(ValueError):
        tile_bounds((0, 0, 1, 1), 0)


def test_merge_overpass_payloads_deduplicates_ways_crossing_tiles():
    merged = merge_overpass_payloads([
        {"osm3s": {"timestamp_osm_base": "2026-07-28T02:00:00Z"},
         "elements": [{"type": "way", "id": 1}, {"type": "way", "id": 2}]},
        {"osm3s": {"timestamp_osm_base": "2026-07-28T03:00:00Z"},
         "elements": [{"type": "way", "id": 2}, {"type": "way", "id": 3}]},
    ])
    assert [e["id"] for e in merged["elements"]] == [1, 2, 3]
    assert merged["osm3s"]["timestamp_osm_base"] == "2026-07-28T03:00:00Z"


def test_neighborhood_indicators_count_zero_change_areas_and_shares():
    units = pd.DataFrame(
        [
            # neighborhood, class, evidence, footprint, post_area, current_area
            ("A", "removed_candidate", "osm_and_spectral", 100.0, 100.0, None),
            ("A", "persistent", "osm_only", 50.0, 50.0, 50.0),
            ("B", "new_candidate", "osm_only", 80.0, None, 80.0),
        ],
        columns=["neighborhood", "reconstruction_class", "evidence", "footprint_area_m2",
                 "post_area_m2", "current_area_m2"],
    )
    table = pd.DataFrame({"neighborhood": ["A", "B", "C"], "area_km2": [1.0, 2.0, 0.5]})
    spectral = {"A": {"valid_m2": 1000.0, "change_m2": 100.0}}
    result = neighborhood_indicators(units, spectral, table).set_index("neighborhood")
    assert result.loc["A", "removed_candidates"] == 1
    assert result.loc["A", "removed_share_of_2023_pct"] == pytest.approx(50.0)
    assert result.loc["A", "net_footprint_area_change_m2"] == pytest.approx(-100.0)
    assert result.loc["A", "removed_spectrally_supported"] == 1
    assert result.loc["A", "spectral_change_share_pct"] == pytest.approx(10.0)
    assert result.loc["B", "new_footprint_density_per_km2"] == pytest.approx(0.5)
    assert np.isnan(result.loc["B", "net_footprint_area_change_pct"])
    assert result.loc["C", "osm_buildings_2023"] == 0
    assert not any("damage" in column for column in result.columns)


# ------------------------------------------------------------------- integration

TIMESTAMPS = {"post_event": "2023-02-24T00:00:00Z", "current": "2026-07-27T00:00:00Z"}
POST_DN = {"blue": 2000, "green": 2200, "red": 2500, "nir": 3000, "swir16": 3500,
           "swir22": 3200}
CHANGED_DN = {"blue": 1400, "green": 1800, "red": 1500, "nir": 5000, "swir16": 3000,
              "swir22": 2000}


def _write_geojson(path: Path, frame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(frame.to_crs(4326).to_json(), encoding="utf-8")


def _snapshot(path: Path, geometries, ids, timestamp):
    import geopandas as gpd

    frame = gpd.GeoSeries(geometries, crs="EPSG:32637").to_crs(4326)
    document = {"type": "FeatureCollection", "features": [
        {"type": "Feature", "id": identifier,
         "properties": {"@osmId": identifier, "@snapshotTimestamp": timestamp},
         "geometry": json.loads(gpd.GeoSeries([geometry], crs=4326).to_json())[
             "features"][0]["geometry"]}
        for identifier, geometry in zip(ids, frame, strict=True)]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")


def test_end_to_end_reconstruction_map_on_synthetic_data(tmp_path):
    gpd = pytest.importorskip("geopandas")
    rasterio = pytest.importorskip("rasterio")
    from rasterio.features import rasterize
    from shapely.geometry import box

    from earthquake_damage.reconstruction_change_analysis import (
        _satellite_config,
        analyze,
    )
    from earthquake_damage.satellite_change_analysis import _aoi_and_grid

    x0, y0 = 390_000.0, 4_245_000.0
    left = box(x0, y0, x0 + 200, y0 + 400)
    right = box(x0 + 200, y0, x0 + 400, y0 + 400)
    neighborhoods = gpd.GeoDataFrame({"mahalle": ["Sol", "Sag"]}, geometry=[left, right],
                                     crs="EPSG:32637")
    _write_geojson(tmp_path / "aoi.geojson", neighborhoods)
    removed = box(x0 + 40, y0 + 40, x0 + 80, y0 + 80)
    persistent_left = box(x0 + 40, y0 + 300, x0 + 70, y0 + 330)
    persistent_right = box(x0 + 300, y0 + 300, x0 + 330, y0 + 330)
    new = box(x0 + 300, y0 + 40, x0 + 340, y0 + 80)
    spectral_only = box(x0 + 120, y0 + 160, x0 + 170, y0 + 210)
    damage = gpd.GeoDataFrame({"damage_grade": ["Destroyed"]}, geometry=[removed.buffer(2)],
                              crs="EPSG:32637")
    _write_geojson(tmp_path / "damage.geojson", damage)
    osm_dir = tmp_path / "osm"
    _snapshot(osm_dir / "buildings_post_event.geojson", [removed, persistent_left, persistent_right],
              ["way/1", "way/2", "way/3"], TIMESTAMPS["post_event"])
    _snapshot(osm_dir / "buildings_current.geojson", [persistent_left, persistent_right, new],
              ["way/2", "way/3", "way/4"], TIMESTAMPS["current"])

    config = json.loads((ROOT / "configs/sprint_00_19.json").read_text(encoding="utf-8"))
    config.update({"aoi": "aoi.geojson", "copernicus": "damage.geojson",
                   "output_directory": "out", "report_directory": "report"})
    config["osm"].update({"snapshot_directory": "osm", "timestamps": TIMESTAMPS})
    config["sentinel2"]["local_raster_directory"] = "rasters"
    flat = _satellite_config(config)
    _, transform, width, height = _aoi_and_grid(tmp_path, flat)
    changed = rasterize([(g, 1) for g in (removed, new, spectral_only)],
                        out_shape=(height, width), transform=transform).astype(bool)
    for role in ("post", "current"):
        directory = tmp_path / "rasters" / role / config["sentinel2"]["scenes"][role]["item_id"]
        directory.mkdir(parents=True)
        for band in ("blue", "green", "red", "nir", "swir16", "swir22", "scl"):
            if band == "scl":
                array = np.full((height, width), 4, dtype="uint16")
            else:
                array = np.full((height, width), POST_DN[band], dtype="uint16")
                if role == "current":
                    array[changed] = CHANGED_DN[band]
            with rasterio.open(directory / f"{band}.tif", "w", driver="GTiff", height=height,
                               width=width, count=1, dtype="uint16", crs="EPSG:32637",
                               transform=transform) as destination:
                destination.write(array, 1)

    report = analyze(tmp_path, config)

    counts = report["osm"]["reconstruction_class_counts"]
    assert counts == {"persistent": 2, "removed_candidate": 1, "new_candidate": 1}
    assert report["sentinel2"]["spectral_only_components"] == 1
    assert report["roundtrip_valid"] is True
    assert report["damage_fields_in_change_outputs"] is False

    change_map = gpd.read_file(tmp_path / "out/reconstruction_change_map.geojson")
    assert "persistent" not in set(change_map["reconstruction_class"])
    assert_no_damage_fields(change_map.columns)
    by_class = change_map.set_index("reconstruction_class")
    assert by_class.loc["removed_candidate", "evidence"] == "osm_and_spectral"
    assert by_class.loc["new_candidate", "evidence"] == "osm_and_spectral"
    assert by_class.loc["removed_candidate", "neighborhood"] == "Sol"
    assert by_class.loc["new_candidate", "neighborhood"] == "Sag"
    assert by_class.loc["spectral_only_change", "direction_hint"] == "vegetation_increase"

    indicators = pd.read_csv(tmp_path / "out/neighborhood_reconstruction_indicators.csv")
    indicators = indicators.set_index("neighborhood")
    assert indicators.loc["Sol", "osm_buildings_2023"] == 2
    assert indicators.loc["Sol", "osm_buildings_2026"] == 1
    assert indicators.loc["Sol", "removed_candidates"] == 1
    assert indicators.loc["Sag", "new_candidates"] == 1
    assert indicators.loc["Sag", "removed_candidates"] == 0

    context = pd.read_csv(tmp_path / "out/reconstruction_vs_emsr648_context.csv")
    assert context.loc[0, "reconstruction_class"] == "removed_candidate"
    assert context.loc[0, "damage_grade"] == "Destroyed"
    assert (tmp_path / "report/reconstruction_validation.json").is_file()
