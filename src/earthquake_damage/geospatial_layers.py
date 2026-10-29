"""Validated, presentation-ready geospatial layers for Sprint 00-12."""

from __future__ import annotations

import json
import math
import unicodedata
from csv import DictReader
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MAP_ROOT = PROJECT_ROOT / "data" / "dashboard" / "sprint_00-12"


class GeospatialLayerError(RuntimeError):
    """Raised when a map layer is missing or violates its data contract."""


@dataclass(frozen=True)
class MapLayers:
    """GeoJSON layers and their audited manifest."""

    neighborhoods: dict[str, Any]
    damage_polygons: dict[str, Any]
    manifest: dict[str, Any]
    validation: dict[str, Any]
    official_coverage: list[dict[str, Any]]
    unmapped_official: list[dict[str, Any]]


def normalize_neighborhood_name(value: object) -> str:
    """Normalize Turkish neighbourhood labels without inventing a match."""
    text = str(value or "").strip().casefold()
    replacements = str.maketrans({"ı": "i", "ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c"})
    text = text.translate(replacements)
    text = "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )
    text = " ".join(
        "".join(character if character.isalnum() else " " for character in text).split()
    )
    for suffix in (" mahallesi", " mahalle", " mah"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
            break
    return text


def normalize_match_key(value: object) -> str:
    """Return the punctuation-free key used by the audited V3 exact-name join."""
    return normalize_neighborhood_name(value).replace(" ", "")


def _iter_positions(coordinates: Any) -> Iterable[tuple[float, float]]:
    if not isinstance(coordinates, list) or not coordinates:
        raise GeospatialLayerError("GeoJSON geometry has empty or malformed coordinates")
    if isinstance(coordinates[0], (int, float)):
        if len(coordinates) < 2:
            raise GeospatialLayerError("GeoJSON position must contain longitude and latitude")
        yield float(coordinates[0]), float(coordinates[1])
        return
    for child in coordinates:
        yield from _iter_positions(child)


def validate_geojson(
    document: dict[str, Any],
    *,
    layer_name: str,
    required_properties: set[str],
    allowed_geometry_types: set[str] | None = None,
) -> dict[str, Any]:
    """Validate the structural, CRS and property contract of a GeoJSON layer."""
    if document.get("type") != "FeatureCollection":
        raise GeospatialLayerError(f"{layer_name}: expected a GeoJSON FeatureCollection")
    if "crs" in document:
        crs_text = json.dumps(document["crs"]).casefold()
        if "4326" not in crs_text and "crs84" not in crs_text:
            raise GeospatialLayerError(
                f"{layer_name}: dashboard layers must use WGS84 longitude/latitude"
            )

    features = document.get("features")
    if not isinstance(features, list) or not features:
        raise GeospatialLayerError(f"{layer_name}: feature collection is empty")

    seen_ids: set[str] = set()
    geometry_types: set[str] = set()
    bbox = [math.inf, math.inf, -math.inf, -math.inf]
    for index, feature in enumerate(features):
        properties = feature.get("properties") or {}
        missing = required_properties.difference(properties)
        if missing:
            raise GeospatialLayerError(
                f"{layer_name}: feature {index} is missing properties: {', '.join(sorted(missing))}"
            )
        feature_id = str(feature.get("id") or properties.get("feature_id") or "")
        if feature_id:
            if feature_id in seen_ids:
                raise GeospatialLayerError(f"{layer_name}: duplicate feature id {feature_id}")
            seen_ids.add(feature_id)

        geometry = feature.get("geometry") or {}
        geometry_type = geometry.get("type")
        geometry_types.add(str(geometry_type))
        if allowed_geometry_types and geometry_type not in allowed_geometry_types:
            raise GeospatialLayerError(
                f"{layer_name}: unsupported geometry type {geometry_type!r} at feature {index}"
            )
        for longitude, latitude in _iter_positions(geometry.get("coordinates")):
            if not (-180 <= longitude <= 180 and -90 <= latitude <= 90):
                raise GeospatialLayerError(
                    f"{layer_name}: coordinate outside WGS84 bounds: {longitude}, {latitude}"
                )
            bbox[0] = min(bbox[0], longitude)
            bbox[1] = min(bbox[1], latitude)
            bbox[2] = max(bbox[2], longitude)
            bbox[3] = max(bbox[3], latitude)

    return {
        "feature_count": len(features),
        "geometry_types": sorted(geometry_types),
        "bbox_wgs84": [round(value, 6) for value in bbox],
        "crs": "EPSG:4326 (RFC 7946 longitude/latitude)",
    }


def read_geojson_checked(
    path: Path,
    *,
    required_properties: set[str],
    allowed_geometry_types: set[str] | None = None,
) -> dict[str, Any]:
    if not path.is_file():
        raise GeospatialLayerError(f"Required map layer is missing: {path}")
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GeospatialLayerError(f"Could not read map layer {path}: {error}") from error
    validate_geojson(
        document,
        layer_name=path.name,
        required_properties=required_properties,
        allowed_geometry_types=allowed_geometry_types,
    )
    return document


def load_map_layers(root: Path = MAP_ROOT) -> MapLayers:
    """Load only committed, audited dashboard layers."""
    neighborhoods = read_geojson_checked(
        root / "aoi05_neighborhoods.geojson",
        required_properties={
            "neighborhood_id",
            "mahalle",
            "official_total",
            "severe_count",
            "severe_ratio",
            "match_method",
            "record_geography",
            "aoi_coverage_ratio",
            "coverage_group",
            "person_01_total",
            "person_01_severe_count",
            "person_02_total",
            "person_02_severe_count",
            "person_03_total",
            "person_03_severe_count",
        },
        allowed_geometry_types={"Polygon", "MultiPolygon"},
    )
    damage_polygons = read_geojson_checked(
        root / "copernicus_damage_polygons.geojson",
        required_properties={"feature_id", "damage_grade", "detection_method", "source"},
        allowed_geometry_types={"Polygon", "MultiPolygon"},
    )
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        validation = json.loads((root / "validation_report.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise GeospatialLayerError(f"Could not read map-layer audit metadata: {error}") from error
    if not validation.get("valid"):
        raise GeospatialLayerError("Committed Sprint 00-12 map layers did not pass validation")
    unmapped_path = root / "unmapped_official_aggregates.csv"
    coverage_path = root / "official_neighborhood_coverage.csv"
    if not coverage_path.is_file():
        raise GeospatialLayerError(f"Required aggregate table is missing: {coverage_path}")
    with coverage_path.open(encoding="utf-8", newline="") as stream:
        official_coverage = list(DictReader(stream))
    coverage_numeric = {
        "official_total": int,
        "severe_count": int,
        "severe_ratio": float,
        "aoi_coverage_ratio": float,
        "person_01_total": int,
        "person_01_severe_count": int,
        "person_02_total": int,
        "person_02_severe_count": int,
        "person_03_total": int,
        "person_03_severe_count": int,
    }
    for index, row in enumerate(official_coverage):
        missing = set(coverage_numeric).difference(row)
        if missing:
            raise GeospatialLayerError(
                f"{coverage_path.name}: row {index} is missing columns: {', '.join(sorted(missing))}"
            )
        for column, converter in coverage_numeric.items():
            row[column] = converter(row[column])

    if not unmapped_path.is_file():
        raise GeospatialLayerError(f"Required aggregate table is missing: {unmapped_path}")
    with unmapped_path.open(encoding="utf-8", newline="") as stream:
        unmapped_official = list(DictReader(stream))
    required_unmapped = {"person", "mahalle", "official_total", "severe_count"}
    for index, row in enumerate(unmapped_official):
        missing = required_unmapped.difference(row)
        if missing:
            raise GeospatialLayerError(
                f"{unmapped_path.name}: row {index} is missing columns: {', '.join(sorted(missing))}"
            )
        row["official_total"] = int(row["official_total"])
        row["severe_count"] = int(row["severe_count"])
        row["severe_ratio"] = float(row["severe_ratio"])
    return MapLayers(
        neighborhoods,
        damage_polygons,
        manifest,
        validation,
        official_coverage,
        unmapped_official,
    )


def filter_feature_collection(
    collection: dict[str, Any],
    *,
    property_name: str,
    accepted_values: set[object],
) -> dict[str, Any]:
    """Return a shallow GeoJSON copy containing features accepted by a UI filter."""
    return {
        **collection,
        "features": [
            feature
            for feature in collection["features"]
            if feature.get("properties", {}).get(property_name) in accepted_values
        ],
    }

