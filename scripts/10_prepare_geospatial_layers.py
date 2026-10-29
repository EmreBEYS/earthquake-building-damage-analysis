"""Build audited, compact Sprint 00-12 dashboard layers from source GeoJSON."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

from earthquake_damage.geospatial_layers import normalize_neighborhood_name, validate_geojson

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OFFICIAL = ROOT / "reports" / "sprint_00-10" / "v3_official_osm_exact_match.csv"
DEFAULT_HIGH_COVERAGE = ROOT / "reports" / "sprint_00-10" / "v3_high_coverage_analysis.csv"
DEFAULT_OUTPUT = ROOT / "data" / "dashboard" / "sprint_00-12"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--neighborhoods", type=Path, required=True)
    parser.add_argument("--copernicus", type=Path, required=True)
    parser.add_argument("--official", type=Path, default=DEFAULT_OFFICIAL)
    parser.add_argument("--high-coverage", type=Path, default=DEFAULT_HIGH_COVERAGE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def _to_wgs84(frame: gpd.GeoDataFrame, label: str) -> gpd.GeoDataFrame:
    if frame.crs is None:
        raise ValueError(f"{label} has no CRS; refusing to guess")
    frame = frame.to_crs(4326)
    if frame.geometry.isna().any() or frame.geometry.is_empty.any():
        raise ValueError(f"{label} contains null or empty geometry")
    invalid = ~frame.geometry.is_valid
    if invalid.any():
        # ``make_valid`` may legally return line remnants for self-touching source
        # polygons. A zero-width buffer keeps this dashboard layer polygonal.
        frame.loc[invalid, "geometry"] = frame.loc[invalid, "geometry"].buffer(0)
    if (~frame.geometry.is_valid).any():
        raise ValueError(f"{label} contains geometry that could not be repaired")
    return frame


def _write_geojson(frame: gpd.GeoDataFrame, path: Path) -> dict:
    document = json.loads(frame.to_json(drop_id=True, to_wgs84=True))
    path.write_text(
        json.dumps(document, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
    )
    return document


def build_neighborhoods(args: argparse.Namespace) -> tuple[dict, dict]:
    boundaries = _to_wgs84(gpd.read_file(args.neighborhoods), "neighborhood boundaries")
    id_column = "id" if "id" in boundaries else "osm_id"
    name_column = "mahalle" if "mahalle" in boundaries else "name"
    if id_column not in boundaries or name_column not in boundaries:
        raise ValueError("neighborhood source must contain id/osm_id and mahalle/name")

    official = pd.read_csv(args.official)
    high = pd.read_csv(args.high_coverage)
    selected_names = set(high["mahalle"])
    official = official[official["mahalle"].isin(selected_names)].copy()
    official["neighborhood_id"] = official["id"].astype(str)
    official["name_key"] = official["mahalle"].map(normalize_neighborhood_name)
    if official["neighborhood_id"].duplicated().any():
        raise ValueError("official aggregate contains duplicate neighborhood ids")

    boundaries["neighborhood_id"] = boundaries[id_column].astype(str)
    boundaries["boundary_name"] = boundaries[name_column].astype(str)
    boundaries["name_key"] = boundaries["boundary_name"].map(normalize_neighborhood_name)
    selected = boundaries.merge(
        official[
            [
                "neighborhood_id",
                "mahalle",
                "name_key",
                "official_total",
                "severe_count",
                "severe_ratio",
            ]
        ],
        on="neighborhood_id",
        how="inner",
        suffixes=("_boundary", "_official"),
        validate="one_to_one",
    )
    if len(selected) != len(official):
        missing = sorted(set(official["neighborhood_id"]) - set(selected["neighborhood_id"]))
        raise ValueError(f"missing boundary geometry for official neighborhood ids: {missing}")
    mismatches = selected[selected["name_key_boundary"] != selected["name_key_official"]]
    if not mismatches.empty:
        pairs = mismatches[["boundary_name", "mahalle"]].to_dict("records")
        raise ValueError(f"neighborhood id/name mismatch: {pairs}")
    normalized_name_match_count = int(
        (selected["name_key_boundary"] == selected["name_key_official"]).sum()
    )

    selected["match_method"] = "exact_osm_relation_id_and_normalized_name"
    selected["record_geography"] = "neighborhood_aggregate_not_building_geolocation"
    selected = selected[
        [
            "neighborhood_id",
            "mahalle",
            "official_total",
            "severe_count",
            "severe_ratio",
            "match_method",
            "record_geography",
            "geometry",
        ]
    ].copy()
    selected["official_total"] = selected["official_total"].astype(int)
    selected["severe_count"] = selected["severe_count"].astype(int)
    selected["severe_ratio"] = selected["severe_ratio"].astype(float)
    selected["geometry"] = selected.geometry.simplify(0.000015, preserve_topology=True)
    document = _write_geojson(selected, args.output / "aoi05_neighborhoods.geojson")
    audit = validate_geojson(
        document,
        layer_name="aoi05_neighborhoods.geojson",
        required_properties={"neighborhood_id", "mahalle", "official_total", "severe_ratio"},
        allowed_geometry_types={"Polygon", "MultiPolygon"},
    )
    audit.update(
        {
            "id_match_count": len(selected),
            "normalized_name_match_count": normalized_name_match_count,
            "official_records": int(selected["official_total"].sum()),
            "building_level_geolocation_claimed": False,
        }
    )
    return document, audit


def build_damage(args: argparse.Namespace) -> tuple[dict, dict]:
    damage = _to_wgs84(gpd.read_file(args.copernicus), "Copernicus damage polygons")
    source_feature_count = len(damage)
    damage = damage[~damage.geometry.is_empty].copy()
    excluded_non_polygonal_or_empty = source_feature_count - len(damage)
    required = {"damage_gra", "det_method"}
    missing = required.difference(damage.columns)
    if missing:
        raise ValueError(f"Copernicus source is missing fields: {sorted(missing)}")
    damage = damage.reset_index(drop=True)
    damage["feature_id"] = [f"EMSR648_AOI05_BLDG_{index + 1:05d}" for index in damage.index]
    damage["damage_grade"] = damage["damage_gra"].fillna("Unknown").astype(str)
    damage["detection_method"] = damage["det_method"].fillna("Unknown").astype(str)
    damage["source"] = "Copernicus EMSR648 AOI05 grading vectors"
    damage = damage[["feature_id", "damage_grade", "detection_method", "source", "geometry"]]
    damage["geometry"] = damage.geometry.simplify(0.000003, preserve_topology=True)
    document = _write_geojson(damage, args.output / "copernicus_damage_polygons.geojson")
    audit = validate_geojson(
        document,
        layer_name="copernicus_damage_polygons.geojson",
        required_properties={"feature_id", "damage_grade", "detection_method", "source"},
        allowed_geometry_types={"Polygon", "MultiPolygon"},
    )
    audit["damage_grade_counts"] = {
        str(key): int(value)
        for key, value in damage["damage_grade"].value_counts().sort_index().items()
    }
    audit["source_feature_count"] = source_feature_count
    audit["excluded_non_polygonal_or_empty"] = excluded_non_polygonal_or_empty
    return document, audit


def main() -> None:
    args = parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    _, neighborhood_audit = build_neighborhoods(args)
    _, damage_audit = build_damage(args)
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat()
    manifest = {
        "sprint": "00-12",
        "generated_at_utc": generated_at,
        "display_crs": "EPSG:4326",
        "layers": {
            "aoi05_neighborhoods": {
                "path": "aoi05_neighborhoods.geojson",
                "source": "OpenStreetMap relation geometries keyed by committed V3 relation ids",
                "source_endpoint": "https://nominatim.openstreetmap.org/lookup",
                "attribution": "© OpenStreetMap contributors, ODbL 1.0",
                "role": "AOI05-intersecting neighborhood boundaries with neighborhood aggregates",
            },
            "copernicus_damage_polygons": {
                "path": "copernicus_damage_polygons.geojson",
                "source": "Copernicus EMSR648 AOI05 GRA builtUpA r1 v1",
                "attribution": "Copernicus Emergency Management Service (© 2023 European Union), EMSR648 Malatya (AOI05): Grading Map",
                "role": "mapped damage polygons; not official structural-safety decisions",
            },
        },
        "official_record_semantics": "neighborhood aggregates only; no building-level geolocation",
    }
    validation = {
        "valid": True,
        "generated_at_utc": generated_at,
        "checks": {
            "aoi05_neighborhoods": neighborhood_audit,
            "copernicus_damage_polygons": damage_audit,
        },
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (args.output / "validation_report.json").write_text(
        json.dumps(validation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
