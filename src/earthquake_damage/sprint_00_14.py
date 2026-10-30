"""Reproducible geometry validation and metric feature pipeline for Sprint 00-14."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import geopandas as gpd
import pandas as pd
import pyogrio

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "sprint_00_14.json"
POLYGON_TYPES = {"Polygon", "MultiPolygon"}


class Sprint0014Error(RuntimeError):
    """Raised when a source or generated layer violates the Sprint 00-14 contract."""


@dataclass(frozen=True)
class PipelineResult:
    buildings: gpd.GeoDataFrame
    neighborhoods: gpd.GeoDataFrame
    report: dict[str, Any]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def load_config(path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise Sprint0014Error(f"Could not read pipeline config {path}: {error}") from error
    required = {
        "sprint",
        "pipeline_version",
        "metric_crs",
        "buildings_source",
        "neighborhoods_source",
        "output_directory",
        "report_path",
        "review_thresholds",
    }
    missing = required.difference(config)
    if missing:
        raise Sprint0014Error(f"Pipeline config is missing keys: {sorted(missing)}")
    return config


def _source_audit(
    frame: gpd.GeoDataFrame,
    *,
    layer_name: str,
    id_column: str,
    required_columns: set[str],
) -> dict[str, Any]:
    missing = required_columns.difference(frame.columns)
    if missing:
        raise Sprint0014Error(f"{layer_name}: missing columns: {sorted(missing)}")
    if frame.crs is None:
        raise Sprint0014Error(f"{layer_name}: source CRS is missing")
    if frame.empty:
        raise Sprint0014Error(f"{layer_name}: source is empty")
    if frame[id_column].isna().any() or frame[id_column].astype(str).str.strip().eq("").any():
        raise Sprint0014Error(f"{layer_name}: null or empty identifiers found")
    duplicate_ids = int(frame[id_column].astype(str).duplicated(keep=False).sum())
    if duplicate_ids:
        raise Sprint0014Error(f"{layer_name}: {duplicate_ids} rows have duplicate identifiers")
    null_count = int(frame.geometry.isna().sum())
    empty_count = int(frame.geometry.is_empty.sum())
    invalid_count = int((~frame.geometry.is_valid).sum())
    geometry_types = set(frame.geom_type.dropna().astype(str))
    unsupported = geometry_types.difference(POLYGON_TYPES)
    if null_count or empty_count or invalid_count or unsupported:
        raise Sprint0014Error(
            f"{layer_name}: unsafe geometry: null={null_count}, empty={empty_count}, "
            f"invalid={invalid_count}, unsupported={sorted(unsupported)}"
        )
    return {
        "feature_count": len(frame),
        "crs": frame.crs.to_string(),
        "geometry_types": sorted(geometry_types),
        "bounds": [round(float(value), 7) for value in frame.total_bounds],
        "null_geometry_count": null_count,
        "empty_geometry_count": empty_count,
        "invalid_geometry_count": invalid_count,
        "duplicate_id_row_count": duplicate_ids,
    }


def _normalized_wkb(geometry: Any) -> str:
    return geometry.normalize().wkb_hex


def _overlap_counts(
    frame: gpd.GeoDataFrame, id_column: str
) -> tuple[pd.Series, list[dict[str, Any]]]:
    left = frame[[id_column, "geometry"]].copy()
    pairs = gpd.sjoin(left, left, predicate="overlaps")
    pairs = pairs[pairs[f"{id_column}_left"] < pairs[f"{id_column}_right"]].copy()
    counts: defaultdict[str, int] = defaultdict(int)
    details: list[dict[str, Any]] = []
    geometry = frame.set_index(id_column).geometry
    for row in pairs.itertuples():
        left_id = str(getattr(row, f"{id_column}_left"))
        right_id = str(getattr(row, f"{id_column}_right"))
        area = float(geometry[left_id].intersection(geometry[right_id]).area)
        counts[left_id] += 1
        counts[right_id] += 1
        details.append(
            {
                "left_id": left_id,
                "right_id": right_id,
                "intersection_area_m2": round(area, 6),
            }
        )
    return frame[id_column].astype(str).map(counts).fillna(0).astype(int), details


def _flag_text(flags: Iterable[tuple[bool, str]]) -> str:
    return ";".join(label for condition, label in flags if condition) or "ok"


def _assign_neighborhoods(
    buildings: gpd.GeoDataFrame, neighborhoods: gpd.GeoDataFrame
) -> pd.DataFrame:
    building_geometry = buildings.geometry
    neighborhood_geometry = neighborhoods.geometry
    points = buildings[["feature_id"]].copy()
    points = gpd.GeoDataFrame(
        points,
        geometry=building_geometry.representative_point(),
        crs=buildings.crs,
    )
    point_matches = gpd.sjoin(
        points,
        neighborhoods[["neighborhood_id", "geometry"]],
        how="left",
        predicate="within",
    ).dropna(subset=["neighborhood_id"])
    point_candidates: defaultdict[int, list[int]] = defaultdict(list)
    for row in point_matches.itertuples():
        point_candidates[int(row.Index)].append(int(row.index_right))

    intersections = gpd.sjoin(
        buildings[["feature_id", "geometry"]],
        neighborhoods[["neighborhood_id", "geometry"]],
        how="left",
        predicate="intersects",
    ).dropna(subset=["neighborhood_id"])
    intersection_candidates: defaultdict[int, list[int]] = defaultdict(list)
    for row in intersections.itertuples():
        intersection_candidates[int(row.Index)].append(int(row.index_right))

    records: list[dict[str, Any]] = []
    for building_index, building in buildings.iterrows():
        point_ids = sorted(set(point_candidates.get(int(building_index), [])))
        intersect_ids = sorted(set(intersection_candidates.get(int(building_index), [])))
        candidate_ids = point_ids or intersect_ids
        selected_index: int | None = None
        method = "unmatched"
        intersection_area = 0.0
        if candidate_ids:
            scored = []
            for neighborhood_index in candidate_ids:
                area = float(
                    building.geometry.intersection(
                        neighborhood_geometry.loc[neighborhood_index]
                    ).area
                )
                neighborhood_id = str(
                    neighborhoods.loc[neighborhood_index, "neighborhood_id"]
                )
                scored.append((area, neighborhood_id, neighborhood_index))
            intersection_area, _, selected_index = max(
                scored, key=lambda item: (item[0], item[1])
            )
            method = "representative_point_within" if point_ids else "maximum_overlap_fallback"
        area_m2 = float(building.geometry.area)
        records.append(
            {
                "feature_id": str(building.feature_id),
                "neighborhood_index": selected_index,
                "neighborhood_id": (
                    str(neighborhoods.loc[selected_index, "neighborhood_id"])
                    if selected_index is not None
                    else None
                ),
                "mahalle": (
                    str(neighborhoods.loc[selected_index, "mahalle"])
                    if selected_index is not None
                    else None
                ),
                "neighborhood_match_method": method,
                "representative_point_match_count": len(point_ids),
                "boundary_intersection_count": len(intersect_ids),
                "containment_ratio": (
                    min(1.0, intersection_area / area_m2)
                    if selected_index is not None and area_m2 > 0
                    else None
                ),
            }
        )
    return pd.DataFrame.from_records(records).set_index("feature_id")


def prepare_frames(
    buildings_source: Path,
    neighborhoods_source: Path,
    *,
    metric_crs: str,
    thresholds: dict[str, float],
) -> PipelineResult:
    buildings_raw = gpd.read_file(buildings_source)
    neighborhoods_raw = gpd.read_file(neighborhoods_source)
    source_audits = {
        "buildings": _source_audit(
            buildings_raw,
            layer_name="buildings",
            id_column="feature_id",
            required_columns={
                "feature_id",
                "damage_grade",
                "detection_method",
                "source",
                "geometry",
            },
        ),
        "neighborhoods": _source_audit(
            neighborhoods_raw,
            layer_name="neighborhoods",
            id_column="neighborhood_id",
            required_columns={"neighborhood_id", "mahalle", "match_method", "geometry"},
        ),
    }
    for name, path in (("buildings", buildings_source), ("neighborhoods", neighborhoods_source)):
        source_audits[name].update({"path": _relative(path), "sha256": sha256_file(path)})

    buildings = buildings_raw.to_crs(metric_crs).reset_index(drop=True)
    neighborhoods = neighborhoods_raw.to_crs(metric_crs).reset_index(drop=True)
    buildings["feature_id"] = buildings["feature_id"].astype(str)
    neighborhoods["neighborhood_id"] = neighborhoods["neighborhood_id"].astype(str)

    buildings["area_m2"] = buildings.geometry.area
    buildings["perimeter_m"] = buildings.geometry.length
    buildings["geometry_valid"] = buildings.geometry.is_valid
    building_wkb = buildings.geometry.map(_normalized_wkb)
    buildings["duplicate_geometry"] = building_wkb.duplicated(keep=False)
    buildings["overlap_count"], building_overlap_pairs = _overlap_counts(
        buildings, "feature_id"
    )
    assignments = _assign_neighborhoods(buildings, neighborhoods)
    buildings = buildings.join(assignments, on="feature_id")
    full_ratio = float(thresholds["full_containment_ratio"])
    minimum_area = float(thresholds["building_area_min_m2"])
    maximum_area = float(thresholds["building_area_max_m2"])
    buildings["quality_flags"] = buildings.apply(
        lambda row: _flag_text(
            (
                (not bool(row.geometry_valid), "invalid_geometry"),
                (bool(row.duplicate_geometry), "duplicate_geometry"),
                (int(row.overlap_count) > 0, "overlaps_building"),
                (float(row.area_m2) < minimum_area, "area_below_review_minimum"),
                (float(row.area_m2) > maximum_area, "area_above_review_maximum"),
                (pd.isna(row.neighborhood_id), "outside_neighborhood_boundaries"),
                (
                    int(row.representative_point_match_count) > 1,
                    "ambiguous_representative_point_match",
                ),
                (int(row.boundary_intersection_count) > 1, "crosses_neighborhood_boundary"),
                (
                    pd.notna(row.containment_ratio)
                    and float(row.containment_ratio) < full_ratio,
                    "partial_neighborhood_containment",
                ),
            )
        ),
        axis=1,
    )

    neighborhoods["area_km2"] = neighborhoods.geometry.area / 1_000_000.0
    neighborhoods["geometry_valid"] = neighborhoods.geometry.is_valid
    neighborhood_wkb = neighborhoods.geometry.map(_normalized_wkb)
    neighborhoods["duplicate_geometry"] = neighborhood_wkb.duplicated(keep=False)
    neighborhoods["overlap_count"], neighborhood_overlap_pairs = _overlap_counts(
        neighborhoods, "neighborhood_id"
    )
    matched_counts = buildings["neighborhood_id"].value_counts()
    neighborhoods["building_count"] = (
        neighborhoods["neighborhood_id"].map(matched_counts).fillna(0).astype(int)
    )
    neighborhoods["building_density_km2"] = (
        neighborhoods["building_count"] / neighborhoods["area_km2"]
    )
    neighborhoods["quality_flags"] = neighborhoods.apply(
        lambda row: _flag_text(
            (
                (not bool(row.geometry_valid), "invalid_geometry"),
                (bool(row.duplicate_geometry), "duplicate_geometry"),
                (int(row.overlap_count) > 0, "overlaps_neighborhood"),
                (float(row.area_km2) <= 0, "nonpositive_area"),
                (int(row.building_count) == 0, "no_matched_buildings"),
            )
        ),
        axis=1,
    )

    building_columns = [
        "feature_id",
        "damage_grade",
        "detection_method",
        "source",
        "area_m2",
        "perimeter_m",
        "neighborhood_id",
        "mahalle",
        "neighborhood_match_method",
        "containment_ratio",
        "representative_point_match_count",
        "boundary_intersection_count",
        "geometry_valid",
        "duplicate_geometry",
        "overlap_count",
        "quality_flags",
        "geometry",
    ]
    neighborhood_columns = [
        "neighborhood_id",
        "mahalle",
        "match_method",
        "area_km2",
        "building_count",
        "building_density_km2",
        "geometry_valid",
        "duplicate_geometry",
        "overlap_count",
        "quality_flags",
        "geometry",
    ]
    buildings = buildings[building_columns].copy()
    neighborhoods = neighborhoods[neighborhood_columns].copy()
    for column in ("area_m2", "perimeter_m", "containment_ratio"):
        buildings[column] = buildings[column].round(6)
    for column in ("area_km2", "building_density_km2"):
        neighborhoods[column] = neighborhoods[column].round(6)

    report = {
        "sprint": "00-14",
        "valid": True,
        "metric_crs": metric_crs,
        "metric_crs_rationale": (
            "WGS 84 / UTM zone 37N covers the Malatya AOI and provides metre units for "
            "area, perimeter, overlap and containment calculations."
        ),
        "sources": source_audits,
        "checks": {
            "building_duplicate_geometry_rows": int(buildings["duplicate_geometry"].sum()),
            "building_overlap_pair_count": len(building_overlap_pairs),
            "building_overlap_pairs": building_overlap_pairs,
            "building_unmatched_count": int(buildings["neighborhood_id"].isna().sum()),
            "building_ambiguous_point_match_count": int(
                (buildings["representative_point_match_count"] > 1).sum()
            ),
            "building_multiple_boundary_intersection_count": int(
                (buildings["boundary_intersection_count"] > 1).sum()
            ),
            "building_partial_containment_count": int(
                (buildings["containment_ratio"].fillna(1.0) < full_ratio).sum()
            ),
            "neighborhood_duplicate_geometry_rows": int(
                neighborhoods["duplicate_geometry"].sum()
            ),
            "neighborhood_overlap_pair_count": len(neighborhood_overlap_pairs),
            "neighborhood_overlap_pairs": neighborhood_overlap_pairs,
            "matched_building_count": int(buildings["neighborhood_id"].notna().sum()),
            "matched_neighborhood_count": int(
                buildings["neighborhood_id"].dropna().nunique()
            ),
        },
        "review_thresholds": thresholds,
        "semantics": {
            "building_layer": (
                "Copernicus mapped damage polygons with geometry-derived metrics; official "
                "assessment records are not joined or transferred."
            ),
            "neighborhood_layer": (
                "Reviewed neighborhood boundaries with counts and density of matched "
                "Copernicus polygons; official damage aggregates are intentionally excluded."
            ),
            "building_level_official_label_transfer": False,
        },
    }
    return PipelineResult(buildings, neighborhoods, report)


def _layer_validation(
    frame: gpd.GeoDataFrame, *, expected_count: int, expected_crs: str
) -> dict[str, Any]:
    crs = frame.crs.to_string() if frame.crs is not None else None
    result = {
        "feature_count": len(frame),
        "crs": crs,
        "geometry_types": sorted(set(frame.geom_type.astype(str))),
        "null_geometry_count": int(frame.geometry.isna().sum()),
        "empty_geometry_count": int(frame.geometry.is_empty.sum()),
        "invalid_geometry_count": int((~frame.geometry.is_valid).sum()),
    }
    if len(frame) != expected_count or crs != expected_crs:
        raise Sprint0014Error(
            f"Output validation failed: expected count/CRS {expected_count}/{expected_crs}, "
            f"got {len(frame)}/{crs}"
        )
    if result["null_geometry_count"] or result["empty_geometry_count"]:
        raise Sprint0014Error(f"Output contains null or empty geometry: {result}")
    if result["invalid_geometry_count"]:
        raise Sprint0014Error(f"Output contains invalid geometry: {result}")
    return result


def validate_outputs(
    *, output_directory: Path, expected_buildings: int, expected_neighborhoods: int, crs: str
) -> dict[str, Any]:
    gpkg = output_directory / "sprint_00-14.gpkg"
    building_parquet = output_directory / "buildings.parquet"
    neighborhood_parquet = output_directory / "neighborhoods.parquet"
    layers = {name for name, _ in pyogrio.list_layers(gpkg)}
    if layers != {"buildings", "neighborhoods"}:
        raise Sprint0014Error(f"GeoPackage layers are incorrect: {sorted(layers)}")
    opened = {
        "gpkg": {
            "path": _relative(gpkg),
            "sha256": sha256_file(gpkg),
            "layers": {
                "buildings": _layer_validation(
                    gpd.read_file(gpkg, layer="buildings"),
                    expected_count=expected_buildings,
                    expected_crs=crs,
                ),
                "neighborhoods": _layer_validation(
                    gpd.read_file(gpkg, layer="neighborhoods"),
                    expected_count=expected_neighborhoods,
                    expected_crs=crs,
                ),
            },
        },
        "geoparquet": {
            "layers": {
                "buildings": _layer_validation(
                    gpd.read_parquet(building_parquet),
                    expected_count=expected_buildings,
                    expected_crs=crs,
                ),
                "neighborhoods": _layer_validation(
                    gpd.read_parquet(neighborhood_parquet),
                    expected_count=expected_neighborhoods,
                    expected_crs=crs,
                ),
            },
            "files": {
                "buildings": {
                    "path": _relative(building_parquet),
                    "sha256": sha256_file(building_parquet),
                },
                "neighborhoods": {
                    "path": _relative(neighborhood_parquet),
                    "sha256": sha256_file(neighborhood_parquet),
                },
            },
        },
    }
    return opened


def write_outputs(result: PipelineResult, output_directory: Path) -> dict[str, Any]:
    output_directory.mkdir(parents=True, exist_ok=True)
    gpkg = output_directory / "sprint_00-14.gpkg"
    building_parquet = output_directory / "buildings.parquet"
    neighborhood_parquet = output_directory / "neighborhoods.parquet"
    for path in (gpkg, building_parquet, neighborhood_parquet):
        if path.exists():
            path.unlink()
    result.buildings.to_file(gpkg, layer="buildings", driver="GPKG", index=False)
    result.neighborhoods.to_file(
        gpkg, layer="neighborhoods", driver="GPKG", mode="a", index=False
    )
    result.buildings.to_parquet(building_parquet, index=False)
    result.neighborhoods.to_parquet(neighborhood_parquet, index=False)
    return validate_outputs(
        output_directory=output_directory,
        expected_buildings=len(result.buildings),
        expected_neighborhoods=len(result.neighborhoods),
        crs=result.buildings.crs.to_string(),
    )


def run_pipeline(config_path: Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    buildings_source = PROJECT_ROOT / config["buildings_source"]
    neighborhoods_source = PROJECT_ROOT / config["neighborhoods_source"]
    output_directory = PROJECT_ROOT / config["output_directory"]
    report_path = PROJECT_ROOT / config["report_path"]
    result = prepare_frames(
        buildings_source,
        neighborhoods_source,
        metric_crs=config["metric_crs"],
        thresholds=config["review_thresholds"],
    )
    report = {
        **result.report,
        "pipeline_version": config["pipeline_version"],
        "outputs": write_outputs(result, output_directory),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
