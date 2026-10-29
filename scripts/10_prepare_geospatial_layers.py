"""Build audited, compact Sprint 00-12 dashboard layers from source GeoJSON."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import geopandas as gpd
import pandas as pd

from earthquake_damage.geospatial_layers import (
    normalize_match_key,
    normalize_neighborhood_name,
    validate_geojson,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_COVERAGE = ROOT / "reports" / "sprint_00-10" / "v3_neighborhood_coverage_validation.csv"
DEFAULT_OFFICIAL_RECORDS = ROOT / "data" / "final" / "malatya_damage_dataset.csv"
DEFAULT_OUTPUT = ROOT / "data" / "dashboard" / "sprint_00-12"
DEFAULT_ALIAS_CONFIG = ROOT / "configs" / "neighborhood_aliases.json"
PERSONS = ("person_01", "person_02", "person_03")
SEVERE_CLASSES = {"Agir hasarli", "Acil yiktirilacak", "Yikik"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--neighborhoods", type=Path, required=True)
    parser.add_argument("--copernicus", type=Path, required=True)
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE)
    parser.add_argument("--official-records", type=Path, default=DEFAULT_OFFICIAL_RECORDS)
    parser.add_argument("--alias-config", type=Path, default=DEFAULT_ALIAS_CONFIG)
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


def build_neighborhoods(args: argparse.Namespace) -> tuple[dict, dict, dict, dict]:
    boundaries = _to_wgs84(gpd.read_file(args.neighborhoods), "neighborhood boundaries")
    id_column = "id" if "id" in boundaries else "osm_id"
    name_column = "mahalle" if "mahalle" in boundaries else "name"
    if id_column not in boundaries or name_column not in boundaries:
        raise ValueError("neighborhood source must contain id/osm_id and mahalle/name")

    official = pd.read_csv(args.coverage)
    records = pd.read_csv(args.official_records, low_memory=False)
    alias_config = json.loads(args.alias_config.read_text(encoding="utf-8"))
    aliases = alias_config["aliases"]
    alias_by_source_key = {
        normalize_match_key(alias["source_name"]): alias for alias in aliases
    }
    if len(alias_by_source_key) != len(aliases):
        raise ValueError("alias config contains duplicate normalized source names")

    official["neighborhood_id"] = official["id"].astype(str)
    official["display_name_key"] = official["mahalle"].map(normalize_neighborhood_name)
    official["match_key"] = official["mahalle"].map(normalize_match_key)
    official["source_name"] = official["mahalle"]
    official["match_method"] = "exact_osm_relation_id_and_normalized_name"
    if official["neighborhood_id"].duplicated().any():
        raise ValueError("official aggregate contains duplicate neighborhood ids")

    records["source_match_key"] = records["mahalle"].map(normalize_match_key)
    records["is_severe"] = records["hasar_durumu"].isin(SEVERE_CLASSES)
    alias_rows: list[dict[str, object]] = []
    for source_key, alias in alias_by_source_key.items():
        subset = records[records["source_match_key"] == source_key]
        if subset.empty:
            raise ValueError(f"confirmed alias has no official records: {alias['source_name']}")
        severe_count = int(subset["is_severe"].sum())
        official_total = len(subset)
        alias_rows.append(
            {
                "id": alias["target_relation_id"],
                "neighborhood_id": alias["target_relation_id"],
                "mahalle": alias["target_name"],
                "display_name_key": normalize_neighborhood_name(alias["target_name"]),
                "match_key": normalize_match_key(alias["target_name"]),
                "source_name": alias["source_name"],
                "match_method": "confirmed_name_alias_and_osm_relation_id",
                "official_total": official_total,
                "severe_count": severe_count,
                "severe_ratio": severe_count / official_total,
                "aoi_coverage_ratio": None,
                "coverage_group": "alias_validated",
            }
        )
    official = pd.concat([official, pd.DataFrame(alias_rows)], ignore_index=True)
    if official["neighborhood_id"].duplicated().any():
        raise ValueError("confirmed aliases collide with an existing neighborhood relation id")

    records["match_key"] = records["source_match_key"]
    for source_key, alias in alias_by_source_key.items():
        records.loc[records["source_match_key"] == source_key, "match_key"] = normalize_match_key(
            alias["target_name"]
        )
    matched_keys = set(official["match_key"])
    matched_records = records[records["match_key"].isin(matched_keys)].copy()
    unmatched_records = records[~records["match_key"].isin(matched_keys)].copy()
    person_values = tuple(sorted(records["person"].dropna().unique()))
    if person_values != PERSONS:
        raise ValueError(f"unexpected person groups: {person_values}")

    person_counts = (
        matched_records.groupby(["match_key", "person"])
        .agg(total=("hasar_durumu", "size"), severe_count=("is_severe", "sum"))
        .reset_index()
    )
    for person in PERSONS:
        subset = person_counts[person_counts["person"] == person].set_index("match_key")
        official[f"{person}_total"] = (
            official["match_key"].map(subset["total"]).fillna(0).astype(int)
        )
        official[f"{person}_severe_count"] = (
            official["match_key"].map(subset["severe_count"]).fillna(0).astype(int)
        )

    calculated_total = official[[f"{person}_total" for person in PERSONS]].sum(axis=1)
    calculated_severe = official[[f"{person}_severe_count" for person in PERSONS]].sum(axis=1)
    if not calculated_total.equals(official["official_total"].astype(int)):
        raise ValueError("person-group totals do not reproduce official neighborhood totals")
    if not calculated_severe.equals(official["severe_count"].astype(int)):
        raise ValueError("person-group severe counts do not reproduce official severe counts")

    person_columns = [
        column for person in PERSONS for column in (f"{person}_total", f"{person}_severe_count")
    ]
    official_table_columns = [
        "neighborhood_id",
        "mahalle",
        "official_total",
        "severe_count",
        "severe_ratio",
        "aoi_coverage_ratio",
        "coverage_group",
        "source_name",
        "match_method",
        *person_columns,
    ]
    official[official_table_columns].to_csv(
        args.output / "official_neighborhood_coverage.csv", index=False, encoding="utf-8"
    )

    unmapped_summary = (
        unmatched_records.groupby(["person", "mahalle"], dropna=False)
        .agg(official_total=("hasar_durumu", "size"), severe_count=("is_severe", "sum"))
        .reset_index()
    )
    unmapped_summary["severe_count"] = unmapped_summary["severe_count"].astype(int)
    unmapped_summary["severe_ratio"] = (
        unmapped_summary["severe_count"] / unmapped_summary["official_total"]
    )
    unmapped_summary["record_geography"] = "unmapped_aggregate_no_validated_boundary"
    unmapped_summary.to_csv(
        args.output / "unmapped_official_aggregates.csv", index=False, encoding="utf-8"
    )

    boundaries["neighborhood_id"] = boundaries[id_column].astype(str)
    boundaries["boundary_name"] = boundaries[name_column].astype(str)
    boundaries["display_name_key"] = boundaries["boundary_name"].map(normalize_neighborhood_name)
    available_ids = set(boundaries["neighborhood_id"])
    mapped_official = official[official["neighborhood_id"].isin(available_ids)].copy()
    if mapped_official.empty:
        raise ValueError("none of the exact-match neighborhoods have boundary geometry")
    selected = boundaries.merge(
        mapped_official[
            [
                "neighborhood_id",
                "mahalle",
                "display_name_key",
                "official_total",
                "severe_count",
                "severe_ratio",
                "aoi_coverage_ratio",
                "coverage_group",
                "source_name",
                "match_method",
                *person_columns,
            ]
        ],
        on="neighborhood_id",
        how="inner",
        suffixes=("_boundary", "_official"),
        validate="one_to_one",
    )
    if len(selected) != len(mapped_official):
        missing = sorted(set(mapped_official["neighborhood_id"]) - set(selected["neighborhood_id"]))
        raise ValueError(f"missing boundary geometry for official neighborhood ids: {missing}")
    mismatches = selected[
        selected["display_name_key_boundary"] != selected["display_name_key_official"]
    ]
    if not mismatches.empty:
        pairs = mismatches[["boundary_name", "mahalle"]].to_dict("records")
        raise ValueError(f"neighborhood id/name mismatch: {pairs}")
    normalized_name_match_count = int(
        (selected["display_name_key_boundary"] == selected["display_name_key_official"]).sum()
    )

    selected["record_geography"] = "neighborhood_aggregate_not_building_geolocation"
    selected = selected[
        [
            "neighborhood_id",
            "mahalle",
            "official_total",
            "severe_count",
            "severe_ratio",
            "aoi_coverage_ratio",
            "coverage_group",
            "source_name",
            *person_columns,
            "match_method",
            "record_geography",
            "geometry",
        ]
    ].copy()
    selected["official_total"] = selected["official_total"].astype(int)
    selected["severe_count"] = selected["severe_count"].astype(int)
    selected["severe_ratio"] = selected["severe_ratio"].astype(float)
    selected["aoi_coverage_ratio"] = pd.to_numeric(
        selected["aoi_coverage_ratio"], errors="coerce"
    )
    selected["geometry"] = selected.geometry.simplify(0.000015, preserve_topology=True)
    document = _write_geojson(selected, args.output / "aoi05_neighborhoods.geojson")
    audit = validate_geojson(
        document,
        layer_name="aoi05_neighborhoods.geojson",
        required_properties={"neighborhood_id", "mahalle", "official_total", "severe_ratio"},
        allowed_geometry_types={"Polygon", "MultiPolygon"},
    )
    requested_ids = set(alias_config["requested_boundary_ids"])
    requested = boundaries[boundaries["neighborhood_id"].isin(requested_ids)].copy()
    missing_requested = sorted(requested_ids - set(requested["neighborhood_id"]))
    if missing_requested:
        raise ValueError(f"requested neighborhood boundaries are missing: {missing_requested}")
    alias_ids = {alias["target_relation_id"] for alias in aliases}
    reference_ids = {item["relation_id"] for item in alias_config["reference_only"]}
    requested["official_match_status"] = requested["neighborhood_id"].map(
        lambda relation_id: (
            "confirmed_name_alias"
            if relation_id in alias_ids
            else "reference_only"
            if relation_id in reference_ids
            else "existing_official_match"
        )
    )
    requested["source"] = "OpenStreetMap contributors via Nominatim lookup"
    requested = requested[
        [
            "neighborhood_id",
            "boundary_name",
            "official_match_status",
            "source",
            "geometry",
        ]
    ].copy()
    requested["geometry"] = requested.geometry.simplify(0.000015, preserve_topology=True)
    requested_document = _write_geojson(
        requested, args.output / "requested_neighborhood_boundaries.geojson"
    )
    requested_audit = validate_geojson(
        requested_document,
        layer_name="requested_neighborhood_boundaries.geojson",
        required_properties={
            "neighborhood_id",
            "boundary_name",
            "official_match_status",
            "source",
        },
        allowed_geometry_types={"Polygon", "MultiPolygon"},
    )
    requested_audit["status_counts"] = {
        str(key): int(value)
        for key, value in requested["official_match_status"].value_counts().sort_index().items()
    }

    audit.update(
        {
            "id_match_count": len(selected),
            "normalized_name_match_count": normalized_name_match_count,
            "official_records": int(selected["official_total"].sum()),
            "official_records_by_person": {
                person: int(selected[f"{person}_total"].sum()) for person in PERSONS
            },
            "exact_match_neighborhoods": int(
                (official["match_method"] == "exact_osm_relation_id_and_normalized_name").sum()
            ),
            "exact_match_official_records": int(
                official.loc[
                    official["match_method"] == "exact_osm_relation_id_and_normalized_name",
                    "official_total",
                ].sum()
            ),
            "exact_match_official_records_by_person": {
                person: int(
                    official.loc[
                        official["match_method"]
                        == "exact_osm_relation_id_and_normalized_name",
                        f"{person}_total",
                    ].sum()
                )
                for person in PERSONS
            },
            "resolved_neighborhoods": len(official),
            "resolved_official_records": int(official["official_total"].sum()),
            "boundary_geometry_unavailable": sorted(
                set(official["neighborhood_id"]) - set(selected["neighborhood_id"])
            ),
            "unmapped_official_records": int(unmapped_summary["official_total"].sum()),
            "unmapped_official_records_by_person": {
                person: int(
                    unmapped_summary.loc[
                        unmapped_summary["person"] == person, "official_total"
                    ].sum()
                )
                for person in PERSONS
            },
            "mapped_coverage_group_counts": {
                str(key): int(value)
                for key, value in selected["coverage_group"].value_counts().sort_index().items()
            },
            "exact_match_coverage_group_counts": {
                str(key): int(value)
                for key, value in official.loc[
                    official["match_method"]
                    == "exact_osm_relation_id_and_normalized_name",
                    "coverage_group",
                ]
                .value_counts()
                .sort_index()
                .items()
            },
            "building_level_geolocation_claimed": False,
            "confirmed_alias_count": len(aliases),
            "confirmed_alias_records": int(sum(row["official_total"] for row in alias_rows)),
        }
    )
    return document, audit, requested_document, requested_audit


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
    _, neighborhood_audit, _, requested_audit = build_neighborhoods(args)
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
                "role": "exact and confirmed-alias neighborhood boundaries with aggregate records",
            },
            "requested_neighborhood_boundaries": {
                "path": "requested_neighborhood_boundaries.geojson",
                "source": "OpenStreetMap relation geometries listed in configs/neighborhood_aliases.json",
                "source_endpoint": "https://nominatim.openstreetmap.org/lookup",
                "attribution": "© OpenStreetMap contributors, ODbL 1.0",
                "role": "reviewed boundary overlay; reference-only features carry no official records",
            },
            "unmapped_official_aggregates": {
                "path": "unmapped_official_aggregates.csv",
                "source": "validated person_01/person_02/person_03 official records",
                "role": "aggregate-only disclosure for records without a validated boundary match",
            },
            "official_neighborhood_coverage": {
                "path": "official_neighborhood_coverage.csv",
                "source": "validated exact-match and AOI coverage reports plus person groups",
                "role": "80 exact-name and 7 confirmed-alias neighborhoods with person-group totals",
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
            "requested_neighborhood_boundaries": requested_audit,
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
