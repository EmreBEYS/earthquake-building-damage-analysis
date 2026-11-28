"""Aligned Sentinel-2 spectral change screening for Sprint 00-18.

Outputs are candidate spectral changes, never building-damage classifications.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

BANDS = ("blue", "green", "red", "nir", "swir16", "swir22", "scl")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_difference(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Return (left-right)/(left+right), with invalid denominators as NaN."""
    left = left.astype("float32", copy=False)
    right = right.astype("float32", copy=False)
    denominator = left + right
    result = np.full(left.shape, np.nan, dtype="float32")
    np.divide(left - right, denominator, out=result, where=np.abs(denominator) > 1e-6)
    return np.clip(result, -1, 1)


def reflectance(dn: np.ndarray, scale: float, offset: float) -> np.ndarray:
    """Convert L2A digital numbers to surface reflectance; DN 0 (no-data) → NaN.

    Processing baseline ≥ 04.00 products carry a -0.1 (DN -1000) offset. Ignoring
    it biases every normalized-difference index, so it is applied explicitly.
    """
    dn = np.asarray(dn)
    result = dn.astype("float32") * np.float32(scale) + np.float32(offset)
    result[dn == 0] = np.nan
    return result


def valid_scl_mask(scl: np.ndarray, invalid_classes: list[int]) -> np.ndarray:
    """Mask no-data, saturated, shadow, cloud/cirrus and snow SCL classes."""
    return ~np.isin(scl, invalid_classes)


def assert_aligned(metadata: list[dict]) -> dict:
    """Reject differing CRS, affine grid, shape or resolution."""
    if not metadata:
        raise ValueError("No raster metadata supplied")
    first = metadata[0]
    keys = ("crs", "transform", "width", "height")
    for item in metadata[1:]:
        if any(item[key] != first[key] for key in keys):
            raise ValueError("Raster grids are not exactly aligned")
    transform = first["transform"]
    if not math.isclose(abs(transform.a), abs(transform.e), abs_tol=1e-9):
        raise ValueError("Raster pixels are not square")
    return first


def _aoi_and_grid(root: Path, config: dict):
    import geopandas as gpd
    from affine import Affine

    aoi = gpd.read_file(root / config["aoi"]).to_crs(config["metric_crs"])
    geometry = aoi.geometry.union_all()
    resolution = float(config["resolution_metres"])
    minx, miny, maxx, maxy = geometry.bounds
    left = math.floor(minx / resolution) * resolution
    bottom = math.floor(miny / resolution) * resolution
    right = math.ceil(maxx / resolution) * resolution
    top = math.ceil(maxy / resolution) * resolution
    width = int(round((right - left) / resolution))
    height = int(round((top - bottom) / resolution))
    transform = Affine(resolution, 0, left, 0, -resolution, top)
    return geometry, transform, width, height


def acquire_clips(root: Path, config: dict) -> dict:
    """Read public COG windows and save only aligned AOI clips outside Git."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.vrt import WarpedVRT

    _, transform, width, height = _aoi_and_grid(root, config)
    directory = root / config["local_raster_directory"]
    records = []
    environment = {
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
    }
    with rasterio.Env(**environment):
        for role, scene in config["scenes"].items():
            scene_dir = directory / role / scene["item_id"]
            scene_dir.mkdir(parents=True, exist_ok=True)
            for asset, spec in config["assets"].items():
                target = scene_dir / f"{asset}.tif"
                source_url = f"{scene['base_url']}/{spec['filename']}"
                if not target.exists():
                    with rasterio.open(source_url) as source:
                        method = getattr(Resampling, spec["resampling"])
                        with WarpedVRT(
                            source,
                            crs=config["metric_crs"],
                            transform=transform,
                            width=width,
                            height=height,
                            resampling=method,
                        ) as vrt:
                            array = vrt.read(1)
                    profile = {
                        "driver": "GTiff",
                        "height": height,
                        "width": width,
                        "count": 1,
                        "dtype": array.dtype,
                        "crs": config["metric_crs"],
                        "transform": transform,
                        "compress": "deflate",
                        "tiled": True,
                        "blockxsize": 256,
                        "blockysize": 256,
                    }
                    with rasterio.open(target, "w", **profile) as destination:
                        destination.write(array, 1)
                records.append(
                    {
                        "role": role,
                        "item_id": scene["item_id"],
                        "datetime": scene["datetime"],
                        "catalog_cloud_cover_percent": scene["catalog_cloud_cover_percent"],
                        "asset": asset,
                        "source_url": source_url,
                        "path": target.relative_to(root).as_posix(),
                        "bytes": target.stat().st_size,
                        "sha256": sha256_file(target),
                    }
                )
    manifest = {
        "status": "acquired",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "records": records,
        "license": config.get("license", "Contains modified Copernicus Sentinel data 2022–2023"),
    }
    manifest_path = directory / "acquisition_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _read_scene(root: Path, config: dict, role: str):
    import rasterio

    arrays = {}
    metadata = []
    for band in BANDS:
        item_id = config["scenes"][role]["item_id"]
        path = root / config["local_raster_directory"] / role / item_id / f"{band}.tif"
        if not path.is_file():
            raise FileNotFoundError(f"Missing spectral clip: {path}")
        with rasterio.open(path) as source:
            arrays[band] = source.read(1)
            metadata.append(
                {
                    "crs": source.crs.to_string(),
                    "transform": source.transform,
                    "width": source.width,
                    "height": source.height,
                }
            )
    return arrays, assert_aligned(metadata)


def _index_stack(scene: dict, scale: float, offset: float) -> dict[str, np.ndarray]:
    red, nir, swir16, swir22 = (
        reflectance(scene[band], scale, offset) for band in ("red", "nir", "swir16", "swir22")
    )
    return {
        "ndvi": normalized_difference(nir, red),
        "ndbi": normalized_difference(swir16, nir),
        "nbr": normalized_difference(nir, swir22),
    }


def analyze(root: Path, config: dict) -> dict:
    """Create candidate-change vectors and EMSR648 spatial comparison metrics."""
    import geopandas as gpd
    import pandas as pd
    from rasterio.features import rasterize, shapes
    from scipy import ndimage
    from shapely.geometry import shape

    aoi_geometry, expected_transform, width, height = _aoi_and_grid(root, config)
    pre, pre_meta = _read_scene(root, config, "pre")
    post, post_meta = _read_scene(root, config, "post")
    grid = assert_aligned([pre_meta, post_meta])
    if grid["crs"] != config["metric_crs"] or grid["transform"] != expected_transform:
        raise ValueError("Raster clips do not match the configured AOI grid")
    if (grid["width"], grid["height"]) != (width, height):
        raise ValueError("Raster clip dimensions do not match the configured AOI grid")

    aoi_mask = rasterize(
        [(aoi_geometry, 1)], out_shape=(height, width), transform=grid["transform"], fill=0
    ).astype(bool)
    pre_clear = valid_scl_mask(pre["scl"], config["scl_invalid_classes"])
    post_clear = valid_scl_mask(post["scl"], config["scl_invalid_classes"])
    reflectance_valid = np.logical_and.reduce(
        [(pre[band] > 0) & (post[band] > 0) for band in BANDS if band != "scl"]
    )
    valid = aoi_mask & pre_clear & post_clear & reflectance_valid
    pre_indices, post_indices = (
        _index_stack(
            scene,
            config["scenes"][role]["reflectance_scale"],
            config["scenes"][role]["reflectance_offset"],
        )
        for role, scene in (("pre", pre), ("post", post))
    )
    deltas = {name: post_indices[name] - pre_indices[name] for name in pre_indices}
    threshold = config["thresholds"]
    signals = (
        (np.abs(deltas["ndvi"]) >= threshold["absolute_delta_ndvi"]).astype("uint8")
        + (np.abs(deltas["ndbi"]) >= threshold["absolute_delta_ndbi"]).astype("uint8")
        + (np.abs(deltas["nbr"]) >= threshold["absolute_delta_nbr"]).astype("uint8")
    )
    built_context = (
        ((pre_indices["ndbi"] > 0) | (post_indices["ndbi"] > 0))
        & ((pre_indices["ndvi"] < 0.5) | (post_indices["ndvi"] < 0.5))
    )
    raw_candidate = valid & built_context & (signals >= threshold["minimum_signals"])
    labels, count = ndimage.label(raw_candidate, structure=np.ones((3, 3), dtype="uint8"))
    sizes = np.bincount(labels.ravel())
    keep = sizes >= int(threshold["minimum_component_pixels"])
    keep[0] = False
    candidate = keep[labels]
    kept_labels = np.flatnonzero(keep)
    component_means = {
        name: dict(
            zip(
                kept_labels,
                ndimage.mean(values, labels=labels, index=kept_labels),
                strict=True,
            )
        )
        for name, values in deltas.items()
    }

    damage = gpd.read_file(root / config["copernicus"]).to_crs(config["metric_crs"])
    damage = damage[damage.geometry.notna() & ~damage.geometry.is_empty].reset_index(drop=True)
    damage_tree = damage.sindex
    change_rows = []
    for number, (geometry_mapping, value) in enumerate(
        shapes(labels.astype("int32"), mask=candidate, transform=grid["transform"]), start=1
    ):
        component_label = int(value)
        geometry = shape(geometry_mapping)
        possible = list(damage_tree.query(geometry, predicate="intersects"))
        overlaps = []
        grades = set()
        for index in possible:
            intersection_area = geometry.intersection(damage.geometry.iloc[index]).area
            if intersection_area > 0:
                overlaps.append(intersection_area)
                grades.add(str(damage.iloc[index].get("damage_grade", "Unknown")))
        change_rows.append(
            {
                "change_id": f"spectral-{number:05d}",
                "status": "spectral_change_candidate",
                "area_m2": float(geometry.area),
                "pixel_count": int(sizes[component_label]),
                "mean_delta_ndvi": float(component_means["ndvi"][component_label]),
                "mean_delta_ndbi": float(component_means["ndbi"][component_label]),
                "mean_delta_nbr": float(component_means["nbr"][component_label]),
                "emsr648_overlap_area_m2": float(sum(overlaps)),
                "emsr648_polygon_count": len(overlaps),
                "emsr648_damage_grades": "; ".join(sorted(grades)),
                "interpretation": "candidate spectral change; not a damage classification",
                "geometry": geometry,
            }
        )
    changes = gpd.GeoDataFrame(change_rows, geometry="geometry", crs=config["metric_crs"])

    zone = rasterize(
        [(geometry, index + 1) for index, geometry in enumerate(damage.geometry)],
        out_shape=candidate.shape,
        transform=grid["transform"],
        fill=0,
        dtype="int32",
        all_touched=True,
    )
    zone_rows = []
    for index, record in damage.iterrows():
        mask = (zone == index + 1) & aoi_mask
        valid_mask = mask & valid
        zone_rows.append(
            {
                "feature_id": record.get("feature_id", f"EMSR648_{index + 1:05d}"),
                "damage_grade": record.get("damage_grade", "Unknown"),
                "footprint_area_m2": float(record.geometry.area),
                "sampled_pixels_all_touched": int(mask.sum()),
                "valid_pixels": int(valid_mask.sum()),
                "candidate_pixels": int((mask & candidate).sum()),
                "candidate_fraction_valid": (
                    float((mask & candidate).sum() / valid_mask.sum())
                    if valid_mask.any()
                    else np.nan
                ),
                "mean_delta_ndvi": (
                    float(np.nanmean(deltas["ndvi"][valid_mask])) if valid_mask.any() else np.nan
                ),
                "mean_delta_ndbi": (
                    float(np.nanmean(deltas["ndbi"][valid_mask])) if valid_mask.any() else np.nan
                ),
                "mean_delta_nbr": (
                    float(np.nanmean(deltas["nbr"][valid_mask])) if valid_mask.any() else np.nan
                ),
            }
        )
    comparison = pd.DataFrame(zone_rows)
    grade_summary = (
        comparison.assign(has_candidate=comparison["candidate_pixels"] > 0)
        .groupby("damage_grade", dropna=False)
        .agg(
            polygons=("feature_id", "count"),
            polygons_with_candidate=("has_candidate", "sum"),
            valid_pixels=("valid_pixels", "sum"),
            candidate_pixels=("candidate_pixels", "sum"),
        )
        .reset_index()
    )
    grade_summary["candidate_fraction_valid"] = (
        grade_summary["candidate_pixels"] / grade_summary["valid_pixels"].replace(0, np.nan)
    )
    output = root / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    map_path = output / "pre_post_change_map.geojson"
    if changes.empty:
        map_path.write_text(
            json.dumps({"type": "FeatureCollection", "features": []}) + "\n", encoding="utf-8"
        )
    else:
        changes.to_crs(4326).to_file(map_path, driver="GeoJSON")
    comparison_path = output / "satellite_emsr648_comparison.csv"
    comparison.to_csv(lineterminator="\n", path_or_buf=comparison_path, index=False)
    reopened_changes = gpd.read_file(map_path)
    reopened_comparison = pd.read_csv(comparison_path)
    if len(reopened_changes) != len(changes) or len(reopened_comparison) != len(comparison):
        raise ValueError("Satellite output roundtrip count mismatch")
    if not reopened_changes.empty and not reopened_changes.geometry.is_valid.all():
        raise ValueError("Satellite change output contains invalid geometry")

    pixel_area = float(config["resolution_metres"]) ** 2
    aoi_pixels = int(aoi_mask.sum())
    valid_pixels = int(valid.sum())
    pre_time = datetime.fromisoformat(config["scenes"]["pre"]["datetime"].replace("Z", "+00:00"))
    post_time = datetime.fromisoformat(
        config["scenes"]["post"]["datetime"].replace("Z", "+00:00")
    )
    report = {
        "status": "completed_candidate_screening",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "scenes": config["scenes"],
        "aoi": config["aoi"],
        "crs": grid["crs"],
        "resolution_metres": config["resolution_metres"],
        "grid": {
            "width": width,
            "height": height,
            "transform": list(grid["transform"])[:6],
            "aligned": True,
        },
        "cloud_mask": {
            "scl_invalid_classes": config["scl_invalid_classes"],
            "pre_invalid_aoi_percent": 100 * float((aoi_mask & ~pre_clear).sum()) / aoi_pixels,
            "post_invalid_aoi_percent": 100 * float((aoi_mask & ~post_clear).sum()) / aoi_pixels,
            "joint_valid_aoi_percent": 100 * valid_pixels / aoi_pixels,
        },
        "rejected_post_scenes_aoi_scl_invalid_percent": config[
            "rejected_post_scenes_aoi_scl_invalid_percent"
        ],
        "reflectance_correction": "DN * scale + offset (offset -0.1 for baseline >= 04.00)",
        "indices": ["NDVI", "NDBI", "NBR"],
        "thresholds": threshold,
        "candidate_components": len(changes),
        "candidate_pixels": int(candidate.sum()),
        "candidate_area_m2": float(candidate.sum() * pixel_area),
        "valid_area_m2": float(valid_pixels * pixel_area),
        "candidate_fraction_of_valid": float(candidate.sum() / valid_pixels),
        "built_context_valid_pixels": int((built_context & valid).sum()),
        "scene_gap_days": (post_time - pre_time).total_seconds() / 86400,
        "emsr648_polygons": len(comparison),
        "emsr648_polygons_with_candidate_pixels": int((comparison.candidate_pixels > 0).sum()),
        "emsr648_by_damage_grade": json.loads(grade_summary.to_json(orient="records")),
        "input_clip_sha256": {
            f"{role}/{band}.tif": sha256_file(
                root
                / config["local_raster_directory"]
                / role
                / config["scenes"][role]["item_id"]
                / f"{band}.tif"
            )
            for role in ("pre", "post")
            for band in BANDS
        },
        "outputs_sha256": {
            map_path.name: sha256_file(map_path),
            comparison_path.name: sha256_file(comparison_path),
        },
        "roundtrip_valid": True,
        "limitations": [
            "Thresholds are conservative screening rules, not locally calibrated damage labels.",
            "Ten-metre pixels are coarser than most buildings and mix roofs, roads and vegetation.",
            "SCL masking cannot remove every haze, shadow or co-registration artefact.",
            f"Scene dates differ by {(post_time - pre_time).days} days and may include seasonal "
            "or non-earthquake change.",
            "EMSR648 overlap is spatial association, not causal validation or accuracy.",
        ],
    }
    report_path = root / "reports/sprint_00-18/satellite_change_validation.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report
