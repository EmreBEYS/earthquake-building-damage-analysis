"""Audited neighborhood-level official damage map for Sprint 00-15."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from earthquake_damage.geospatial_layers import (
    GeospatialLayerError,
    normalize_match_key,
    read_geojson_checked,
    validate_geojson,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sprint_00_15.json"
OUTPUT_ROOT = PROJECT_ROOT / "data" / "dashboard" / "sprint_00-15"

OFFICIAL_SEVERE_RATIO_BANDS = (
    {
        "key": "low",
        "label": "Düşük · %0–10",
        "minimum": 0.0,
        "maximum": 0.10,
        "color": "#2ca25f",
    },
    {
        "key": "elevated",
        "label": "Yükselmiş · %10–25",
        "minimum": 0.10,
        "maximum": 0.25,
        "color": "#fee08b",
    },
    {
        "key": "high",
        "label": "Yüksek · %25–40",
        "minimum": 0.25,
        "maximum": 0.40,
        "color": "#f46d43",
    },
    {
        "key": "very_high",
        "label": "Çok yüksek · %40+",
        "minimum": 0.40,
        "maximum": None,
        "color": "#a50026",
    },
)


class RealDamageMapError(RuntimeError):
    """Raised when Sprint 00-15 inputs or outputs violate their contract."""


def official_severe_ratio_band(ratio: float) -> dict[str, Any]:
    """Classify the combined heavy/urgent/destroyed official-record share."""
    if not 0 <= ratio <= 1:
        raise ValueError("Official severe-damage ratio must be between 0 and 1")
    for band in OFFICIAL_SEVERE_RATIO_BANDS:
        maximum = band["maximum"]
        if maximum is None or ratio < maximum:
            return band
    raise AssertionError("The final severe-ratio band must be open-ended")


@dataclass(frozen=True)
class RealDamageMap:
    """Independent official and Copernicus map layers plus audit metadata."""

    official_neighborhoods: dict[str, Any]
    copernicus_damage: dict[str, Any]
    neighborhood_stats: pd.DataFrame
    manifest: dict[str, Any]
    validation: dict[str, Any]
    config: dict[str, Any]


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RealDamageMapError(f"Could not read Sprint 00-15 config {path}: {error}") from error


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def coordinate_evidence_columns(columns: Iterable[str]) -> list[str]:
    """Return only explicit coordinate/geometry evidence, never address text fields."""
    available = {str(column).casefold() for column in columns}
    evidence: list[str] = []
    for latitude, longitude in (("latitude", "longitude"), ("lat", "lon"), ("y", "x")):
        if {latitude, longitude}.issubset(available):
            evidence.extend([latitude, longitude])
    if "geometry" in available:
        evidence.append("geometry")
    return sorted(set(evidence))


def _load_official_records(project_root: Path, config: dict[str, Any]) -> pd.DataFrame:
    paths = sorted(project_root.glob(config["official_records_glob"]))
    if not paths:
        raise RealDamageMapError(
            "No processed official records were found. Reproduce Sprint 00-09 outputs first."
        )
    frames = []
    required = {"person", "mahalle", "hasar_durumu", "source_pdf", "source_page"}
    for path in paths:
        frame = pd.read_csv(path)
        missing = required.difference(frame.columns)
        if missing:
            raise RealDamageMapError(
                f"{path.name} is missing columns: {', '.join(sorted(missing))}"
            )
        frames.append(frame)
    records = pd.concat(frames, ignore_index=True)
    if len(records) != config["expected_official_records"]:
        raise RealDamageMapError(
            f"Expected {config['expected_official_records']} official records, found {len(records)}"
        )
    return records


def aggregate_official_records(
    records: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    """Aggregate official PDF records by reviewed neighborhood and six damage classes."""
    class_map = {item["source_label"]: item["key"] for item in config["official_classes"]}
    unknown = sorted(set(records["hasar_durumu"].dropna()) - set(class_map))
    if unknown:
        raise RealDamageMapError(f"Unknown official damage classes: {unknown}")

    working = records[["mahalle", "hasar_durumu"]].copy()
    working["match_key"] = working["mahalle"].map(normalize_match_key)
    working["damage_key"] = working["hasar_durumu"].map(class_map)
    counts = (
        working.groupby(["match_key", "damage_key"], dropna=False)
        .size()
        .unstack(fill_value=0)
    )
    for item in config["official_classes"]:
        if item["key"] not in counts:
            counts[item["key"]] = 0
    counts = counts[[item["key"] for item in config["official_classes"]]].astype(int)
    counts["official_total"] = counts.sum(axis=1)
    counts["severe_count"] = counts[config["severe_classes"]].sum(axis=1)
    counts["severe_ratio"] = counts["severe_count"] / counts["official_total"]
    return counts.reset_index()


def build_official_neighborhood_layer(
    boundaries: dict[str, Any],
    aggregates: pd.DataFrame,
    config: dict[str, Any],
    alias_targets: dict[str, str] | None = None,
) -> tuple[dict[str, Any], pd.DataFrame]:
    """Attach aggregates to reviewed boundaries without inventing building coordinates."""
    aggregate_lookup = aggregates.set_index("match_key").to_dict(orient="index")
    features: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    unmatched_boundaries: list[str] = []
    matched_keys: set[str] = set()
    class_keys = [item["key"] for item in config["official_classes"]]

    alias_targets = alias_targets or {}
    for feature in boundaries["features"]:
        properties = feature["properties"]
        match_key = normalize_match_key(properties.get("source_name") or properties["mahalle"])
        aggregate = aggregate_lookup.get(match_key)
        if aggregate is None:
            unmatched_boundaries.append(properties["mahalle"])
            continue
        matched_keys.add(match_key)
        dominant_key = max(class_keys, key=lambda key: (int(aggregate[key]), -class_keys.index(key)))
        neighborhood_id = properties["neighborhood_id"]
        display_name = alias_targets.get(neighborhood_id, properties["mahalle"])
        mapped = {
            "neighborhood_id": neighborhood_id,
            "mahalle": display_name,
            "mapping_level": "neighborhood",
            "coordinate_evidence": False,
            "source": "Official Ministry damage-assessment PDF records",
            "official_total": int(aggregate["official_total"]),
            "severe_count": int(aggregate["severe_count"]),
            "severe_ratio": float(aggregate["severe_ratio"]),
            "dominant_damage_class": dominant_key,
            **{key: int(aggregate[key]) for key in class_keys},
        }
        rows.append(mapped)
        features.append(
            {
                "type": "Feature",
                "id": neighborhood_id,
                "properties": mapped,
                "geometry": feature["geometry"],
            }
        )

    unmatched_records = sorted(set(aggregate_lookup) - matched_keys)
    if unmatched_boundaries or unmatched_records:
        raise RealDamageMapError(
            "Official/boundary neighborhood mismatch: "
            f"boundaries={unmatched_boundaries}, records={unmatched_records}"
        )
    collection = {
        "type": "FeatureCollection",
        "name": "official_damage_neighborhood_aggregates",
        "crs": {"type": "name", "properties": {"name": "EPSG:4326"}},
        "metadata": {
            "mapping_level": "neighborhood",
            "building_level_geolocation_claimed": False,
            "coordinate_evidence": False,
        },
        "features": features,
    }
    return collection, pd.DataFrame(rows)


def _write_json(path: Path, document: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def prepare_real_damage_map(project_root: Path = PROJECT_ROOT) -> dict[str, Any]:
    """Build, validate and audit the Sprint 00-15 dashboard artifacts."""
    config_path = project_root / "configs" / "sprint_00_15.json"
    config = load_config(config_path)
    records = _load_official_records(project_root, config)
    evidence = coordinate_evidence_columns(records.columns)
    if evidence:
        raise RealDamageMapError(
            "Coordinate evidence was detected. A reviewed building-level workflow is required "
            f"before mapping these fields: {evidence}"
        )

    boundaries_path = project_root / config["official_boundary_layer"]
    aliases_path = project_root / config["neighborhood_aliases"]
    copernicus_path = project_root / config["copernicus_layer"]
    boundaries = read_geojson_checked(
        boundaries_path,
        required_properties={"neighborhood_id", "mahalle"},
        allowed_geometry_types={"Polygon", "MultiPolygon"},
    )
    copernicus = read_geojson_checked(
        copernicus_path,
        required_properties={"feature_id", "damage_grade", "source"},
        allowed_geometry_types={"Polygon", "MultiPolygon"},
    )
    aggregates = aggregate_official_records(records, config)
    try:
        aliases_document = json.loads(aliases_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RealDamageMapError(f"Could not read reviewed neighborhood aliases: {error}") from error
    alias_targets = {
        item["target_relation_id"]: item["target_name"] for item in aliases_document["aliases"]
    }
    official_layer, stats = build_official_neighborhood_layer(
        boundaries, aggregates, config, alias_targets
    )

    output_root = project_root / config["output_root"]
    output_root.mkdir(parents=True, exist_ok=True)
    official_path = output_root / "official_damage_neighborhoods.geojson"
    stats_path = output_root / "official_neighborhood_statistics.csv"
    manifest_path = output_root / "manifest.json"
    validation_path = output_root / "validation_report.json"
    _write_json(official_path, official_layer)
    stats.sort_values("official_total", ascending=False).to_csv(stats_path, index=False)

    class_totals = {
        item["key"]: int(records["hasar_durumu"].eq(item["source_label"]).sum())
        for item in config["official_classes"]
    }
    manifest = {
        "sprint": "00-15",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "official_mapping_level": "neighborhood",
        "official_coordinate_evidence": False,
        "building_level_official_geolocation_claimed": False,
        "source_separation": {
            "joined_at_building_level": False,
            "official": {
                "role": "neighborhood aggregates from official PDF records",
                "layer": official_path.relative_to(project_root).as_posix(),
            },
            "copernicus": {
                "role": "independent EMSR648 mapped-damage polygons",
                "layer": copernicus_path.relative_to(project_root).as_posix(),
            },
        },
        "satellite_basemap": config["satellite_basemap"],
        "inputs": {
            "official_records": config["official_records_glob"],
            "official_boundaries": boundaries_path.relative_to(project_root).as_posix(),
            "neighborhood_aliases": aliases_path.relative_to(project_root).as_posix(),
            "copernicus_damage": copernicus_path.relative_to(project_root).as_posix(),
        },
        "outputs": {
            "official_layer": official_path.relative_to(project_root).as_posix(),
            "statistics": stats_path.relative_to(project_root).as_posix(),
        },
    }
    _write_json(manifest_path, manifest)

    geojson_audit = validate_geojson(
        official_layer,
        layer_name=official_path.name,
        required_properties={
            "neighborhood_id",
            "mahalle",
            "mapping_level",
            "coordinate_evidence",
            "official_total",
            *class_totals,
        },
        allowed_geometry_types={"Polygon", "MultiPolygon"},
    )
    validation = {
        "sprint": "00-15",
        "valid": True,
        "official_record_count": len(records),
        "official_neighborhood_count": len(stats),
        "official_class_totals": class_totals,
        "official_coordinate_evidence_columns": evidence,
        "building_level_official_geolocation_claimed": False,
        "copernicus_feature_count": len(copernicus["features"]),
        "sources_joined_at_building_level": False,
        "geojson": geojson_audit,
        "sha256": {
            "config": file_sha256(config_path),
            "official_boundaries": file_sha256(boundaries_path),
            "neighborhood_aliases": file_sha256(aliases_path),
            "copernicus_damage": file_sha256(copernicus_path),
            "official_layer": file_sha256(official_path),
            "statistics": file_sha256(stats_path),
            "manifest": file_sha256(manifest_path),
        },
    }
    expected = {
        "official_record_count": config["expected_official_records"],
        "official_neighborhood_count": config["expected_neighborhoods"],
        "copernicus_feature_count": config["expected_copernicus_features"],
    }
    for field, expected_value in expected.items():
        if validation[field] != expected_value:
            raise RealDamageMapError(
                f"{field}: expected {expected_value}, found {validation[field]}"
            )
    _write_json(validation_path, validation)
    return validation


def load_real_damage_map(
    project_root: Path = PROJECT_ROOT, output_root: Path | None = None
) -> RealDamageMap:
    """Load the committed Sprint 00-15 layer contract for Streamlit."""
    config = load_config(project_root / "configs" / "sprint_00_15.json")
    root = output_root or project_root / config["output_root"]
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        validation = json.loads((root / "validation_report.json").read_text(encoding="utf-8"))
        stats = pd.read_csv(root / "official_neighborhood_statistics.csv")
    except (OSError, json.JSONDecodeError, pd.errors.ParserError) as error:
        raise RealDamageMapError(f"Could not load Sprint 00-15 artifacts: {error}") from error
    if not validation.get("valid"):
        raise RealDamageMapError("Sprint 00-15 artifacts did not pass validation")

    official = read_geojson_checked(
        root / "official_damage_neighborhoods.geojson",
        required_properties={
            "neighborhood_id",
            "mahalle",
            "mapping_level",
            "coordinate_evidence",
            "official_total",
            *{item["key"] for item in config["official_classes"]},
        },
        allowed_geometry_types={"Polygon", "MultiPolygon"},
    )
    copernicus_path = project_root / config["copernicus_layer"]
    try:
        copernicus = read_geojson_checked(
            copernicus_path,
            required_properties={"feature_id", "damage_grade", "source"},
            allowed_geometry_types={"Polygon", "MultiPolygon"},
        )
    except GeospatialLayerError as error:
        raise RealDamageMapError(str(error)) from error
    return RealDamageMap(official, copernicus, stats, manifest, validation, config)

