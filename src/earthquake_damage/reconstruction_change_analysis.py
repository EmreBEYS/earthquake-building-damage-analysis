"""Sprint 00-19: physical reconstruction change, 24 Feb 2023 → 2026.

Two independent evidence streams are combined conservatively:

* dated OpenStreetMap footprint snapshots (Overpass attic ``[date:]`` queries; the
  ohsome extraction endpoints answered HTTP 403), matched one-to-one
  with the Sprint 00-18 IoU rules, give *removed* and *newly appearing* footprint
  candidates; and
* aligned Sentinel-2 L2A reflectance (offset-corrected) gives a per-footprint
  spectral-change fraction and unattributed spectral-change components.

Outputs describe change in the mapped/observed built environment. They are never
damage classes: damage attributes are not joined into the change map or the
neighbourhood indicators, and the EMSR648 co-occurrence table is kept separate.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

from earthquake_damage.building_change_analysis import (
    load_snapshot,
    match_buildings,
    prepare_frame,
    sha256,
)
from earthquake_damage.overpass_snapshots import (  # noqa: F401 - re-exported for tests
    download_snapshot,
    merge_overpass_payloads,
    overpass_query,
    overpass_to_geojson,
    tile_bounds,
)
from earthquake_damage.satellite_change_analysis import (
    BANDS,
    _aoi_and_grid,
    _read_scene,
    acquire_clips,
    assert_aligned,
    normalized_difference,
    reflectance,
    sha256_file,
    valid_scl_mask,
)

OSM_TO_RECONSTRUCTION = {
    "unmatched": "removed_candidate",
    "newly_mapped": "new_candidate",
    "geometry_changed": "modified_candidate",
    "unchanged": "persistent",
    "uncertain": "uncertain",
}
RECONSTRUCTION_CLASSES = (
    "removed_candidate",
    "new_candidate",
    "modified_candidate",
    "persistent",
    "uncertain",
    "spectral_only_change",
)
CLASS_LABELS_TR = {
    "removed_candidate": "Kaldırılmış yapı adayı",
    "new_candidate": "Yeni görünen yapı adayı",
    "modified_candidate": "Geometrisi değişen yapı",
    "persistent": "Varlığını sürdüren yapı",
    "uncertain": "Belirsiz eşleşme",
    "spectral_only_change": "Yalnız spektral değişim",
}
# Change outputs must never carry a damage attribute; that would conflate the two.
FORBIDDEN_DAMAGE_TOKENS = ("damage", "hasar", "grade", "emsr", "severity", "collapsed", "yikik")
ROLES = ("post", "current")


# ---------------------------------------------------------------------------
# Pure, unit-tested building blocks
# ---------------------------------------------------------------------------


def bare_soil_index(
    blue: np.ndarray, red: np.ndarray, nir: np.ndarray, swir16: np.ndarray
) -> np.ndarray:
    """BSI = ((SWIR1 + Red) − (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))."""
    return normalized_difference(
        np.asarray(swir16, dtype="float32") + np.asarray(red, dtype="float32"),
        np.asarray(nir, dtype="float32") + np.asarray(blue, dtype="float32"),
    )


def index_stack(scene: dict[str, np.ndarray], scale: float, offset: float) -> dict:
    bands = {
        name: reflectance(scene[name], scale, offset)
        for name in ("blue", "red", "nir", "swir16")
    }
    return {
        "ndvi": normalized_difference(bands["nir"], bands["red"]),
        "ndbi": normalized_difference(bands["swir16"], bands["nir"]),
        "bsi": bare_soil_index(bands["blue"], bands["red"], bands["nir"], bands["swir16"]),
    }


def change_signal_count(deltas: dict[str, np.ndarray], thresholds: dict) -> np.ndarray:
    """Count how many of |ΔNDVI|, |ΔNDBI|, |ΔBSI| reach their thresholds (NaN → 0)."""
    total = np.zeros(np.shape(deltas["ndvi"]), dtype="uint8")
    for name in ("ndvi", "ndbi", "bsi"):
        values = np.nan_to_num(np.abs(deltas[name]), nan=0.0)
        total += (values >= thresholds[f"absolute_delta_{name}"]).astype("uint8")
    return total


def direction_hint(delta_ndvi: float, delta_ndbi: float, delta_bsi: float) -> str:
    """Descriptive dominant spectral direction; never a construction/demolition label."""
    values = {"ndvi": delta_ndvi, "ndbi": delta_ndbi, "bsi": delta_bsi}
    if any(value is None or not np.isfinite(value) for value in values.values()):
        return "insufficient_data"
    name = max(values, key=lambda key: abs(values[key]))
    sign = "increase" if values[name] > 0 else "decrease"
    return {"ndvi": "vegetation", "ndbi": "built_index", "bsi": "bare_soil_index"}[
        name
    ] + f"_{sign}"


def classify_footprint(
    osm_status: str, valid_pixels: int, candidate_pixels: int, support_fraction: float
) -> tuple[str, str, float | None]:
    """Map an OSM match status to a reconstruction class plus evidence level.

    Evidence is ``osm_and_spectral`` only when enough cloud-free pixels inside the
    footprint show multi-index change. The class itself is never upgraded or
    downgraded by the spectral stream, so the two sources remain auditable.
    """
    if osm_status not in OSM_TO_RECONSTRUCTION:
        raise ValueError(f"Unknown OSM match status: {osm_status}")
    if not 0 < support_fraction <= 1:
        raise ValueError("support_fraction must be in (0, 1]")
    reconstruction_class = OSM_TO_RECONSTRUCTION[osm_status]
    if valid_pixels <= 0:
        return reconstruction_class, "osm_only_no_clear_pixels", None
    fraction = candidate_pixels / valid_pixels
    evidence = "osm_and_spectral" if fraction >= support_fraction else "osm_only"
    return reconstruction_class, evidence, float(fraction)


def assert_no_damage_fields(columns) -> None:
    """Reject any damage-like column in change outputs (scope guard of Sprint 00-19)."""
    offending = [
        column
        for column in columns
        if any(token in str(column).lower() for token in FORBIDDEN_DAMAGE_TOKENS)
    ]
    if offending:
        raise ValueError(f"Change outputs must not carry damage fields: {offending}")


def neighborhood_indicators(units, spectral_by_neighborhood, neighborhoods):
    """Aggregate reconstruction units into per-neighbourhood construction indicators.

    ``units`` needs columns neighborhood, reconstruction_class, evidence, side
    (``post``/``current``/``both``), footprint_area_m2, post_area_m2, current_area_m2.
    ``spectral_by_neighborhood`` holds valid/change pixel areas; ``neighborhoods``
    holds the neighbourhood name and area (km²). Every neighbourhood is reported,
    including those without change, so zero means "observed, no candidate".
    """
    import pandas as pd

    rows = []
    for _, area_row in neighborhoods.iterrows():
        name = area_row["neighborhood"]
        subset = units[units["neighborhood"] == name]
        removed = subset[subset["reconstruction_class"] == "removed_candidate"]
        new = subset[subset["reconstruction_class"] == "new_candidate"]
        post_count = int(subset["post_area_m2"].notna().sum())
        current_count = int(subset["current_area_m2"].notna().sum())
        post_area = float(subset["post_area_m2"].sum())
        current_area = float(subset["current_area_m2"].sum())
        spectral = spectral_by_neighborhood.get(name, {"valid_m2": 0.0, "change_m2": 0.0})
        rows.append(
            {
                "neighborhood": name,
                "area_km2": float(area_row["area_km2"]),
                "osm_buildings_2023": post_count,
                "osm_buildings_2026": current_count,
                "footprint_area_2023_m2": post_area,
                "footprint_area_2026_m2": current_area,
                "net_footprint_area_change_m2": current_area - post_area,
                "net_footprint_area_change_pct": (
                    100 * (current_area - post_area) / post_area if post_area else np.nan
                ),
                "removed_candidates": len(removed),
                "removed_area_m2": float(removed["footprint_area_m2"].sum()),
                "removed_share_of_2023_pct": (
                    100 * len(removed) / post_count if post_count else np.nan
                ),
                "removed_spectrally_supported": int(
                    (removed["evidence"] == "osm_and_spectral").sum()
                ),
                "new_candidates": len(new),
                "new_area_m2": float(new["footprint_area_m2"].sum()),
                "new_share_of_2026_pct": (
                    100 * len(new) / current_count if current_count else np.nan
                ),
                "new_spectrally_supported": int((new["evidence"] == "osm_and_spectral").sum()),
                "new_footprint_density_per_km2": (
                    len(new) / area_row["area_km2"] if area_row["area_km2"] else np.nan
                ),
                "modified_candidates": int(
                    (subset["reconstruction_class"] == "modified_candidate").sum()
                ),
                "persistent": int((subset["reconstruction_class"] == "persistent").sum()),
                "uncertain": int((subset["reconstruction_class"] == "uncertain").sum()),
                "renewal_turnover_pct": (
                    100
                    * (float(removed["footprint_area_m2"].sum()) + float(new["footprint_area_m2"].sum()))
                    / post_area
                    if post_area
                    else np.nan
                ),
                "spectral_valid_area_m2": float(spectral["valid_m2"]),
                "spectral_change_area_m2": float(spectral["change_m2"]),
                "spectral_change_share_pct": (
                    100 * spectral["change_m2"] / spectral["valid_m2"]
                    if spectral["valid_m2"]
                    else np.nan
                ),
            }
        )
    frame = pd.DataFrame(rows).sort_values("neighborhood").reset_index(drop=True)
    assert_no_damage_fields(frame.columns)
    return frame


# ---------------------------------------------------------------------------
# Acquisition
# ---------------------------------------------------------------------------


def _satellite_config(config: dict) -> dict:
    """Flatten the Sprint 00-19 config into the Sprint 00-18 raster helper format."""
    sentinel = config["sentinel2"]
    return {
        "aoi": config["aoi"],
        "metric_crs": config["metric_crs"],
        "resolution_metres": sentinel["resolution_metres"],
        "local_raster_directory": sentinel["local_raster_directory"],
        "scenes": sentinel["scenes"],
        "assets": sentinel["assets"],
        "license": sentinel["license"],
    }


def aoi_wgs84(root: Path, config: dict):
    import geopandas as gpd

    neighborhoods = gpd.read_file(root / config["aoi"]).to_crs(4326)
    return neighborhoods.geometry.union_all()


def acquire_osm_snapshots(root: Path, config: dict) -> list[dict]:
    """Download immutable dated Overpass snapshots for both timestamps with provenance."""
    osm = config["osm"]
    directory = root / osm["snapshot_directory"]
    bounds = aoi_wgs84(root, config).bounds
    return [
        download_snapshot(
            directory / f"buildings_{role}.geojson",
            bounds,
            timestamp,
            osm["endpoints"],
            int(osm.get("tiles_per_axis", 4)),
            role,
            load_snapshot,
        )
        for role, timestamp in osm["timestamps"].items()
    ]


def screen_current_scenes(root: Path, config: dict) -> dict[str, float]:
    """AOI-specific SCL invalid share for each candidate 2026 scene (selection evidence)."""
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.features import rasterize
    from rasterio.vrt import WarpedVRT

    flat = _satellite_config(config)
    geometry, transform, width, height = _aoi_and_grid(root, flat)
    aoi = rasterize([(geometry, 1)], out_shape=(height, width), transform=transform).astype(bool)
    invalid_classes = config["sentinel2"]["scl_invalid_classes"]
    result = {}
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR"):
        for item_id, base_url in config["sentinel2"]["screened_current_candidates"].items():
            with rasterio.open(f"{base_url}/SCL.tif") as source, WarpedVRT(
                source,
                crs=flat["metric_crs"],
                transform=transform,
                width=width,
                height=height,
                resampling=Resampling.nearest,
            ) as vrt:
                scl = vrt.read(1)
            invalid = aoi & ~valid_scl_mask(scl, invalid_classes)
            result[item_id] = round(100 * float(invalid.sum()) / float(aoi.sum()), 3)
    return result


def acquire(root: Path, config: dict) -> dict:
    manifest = acquire_clips(root, _satellite_config(config))
    osm_records = acquire_osm_snapshots(root, config)
    return {"osm": osm_records, "sentinel2_clips": len(manifest["records"])}


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def _spectral_change(root: Path, config: dict) -> dict:
    """Aligned, offset-corrected 2023→2026 multi-index change rasters."""
    from rasterio.features import rasterize
    from scipy import ndimage

    flat = _satellite_config(config)
    aoi_geometry, expected_transform, width, height = _aoi_and_grid(root, flat)
    scenes, metadata = {}, []
    for role in ROLES:
        scenes[role], meta = _read_scene(root, flat, role)
        metadata.append(meta)
    grid = assert_aligned(metadata)
    if grid["crs"] != flat["metric_crs"] or grid["transform"] != expected_transform:
        raise ValueError("Raster clips do not match the configured AOI grid")
    if (grid["width"], grid["height"]) != (width, height):
        raise ValueError("Raster clip dimensions do not match the configured AOI grid")
    sentinel = config["sentinel2"]
    aoi_mask = rasterize(
        [(aoi_geometry, 1)], out_shape=(height, width), transform=grid["transform"], fill=0
    ).astype(bool)
    clear = {
        role: valid_scl_mask(scenes[role]["scl"], sentinel["scl_invalid_classes"])
        for role in ROLES
    }
    reflectance_valid = np.logical_and.reduce(
        [scenes[role][band] > 0 for role in ROLES for band in BANDS if band != "scl"]
    )
    valid = aoi_mask & clear["post"] & clear["current"] & reflectance_valid
    indices = {
        role: index_stack(
            scenes[role],
            sentinel["scenes"][role]["reflectance_scale"],
            sentinel["scenes"][role]["reflectance_offset"],
        )
        for role in ROLES
    }
    deltas = {name: indices["current"][name] - indices["post"][name] for name in indices["post"]}
    thresholds = sentinel["thresholds"]
    signals = change_signal_count(deltas, thresholds)
    built_context = (
        (np.nan_to_num(indices["post"]["ndbi"], nan=-1) > 0)
        | (np.nan_to_num(indices["current"]["ndbi"], nan=-1) > 0)
    ) & (
        (np.nan_to_num(indices["post"]["ndvi"], nan=1) < 0.5)
        | (np.nan_to_num(indices["current"]["ndvi"], nan=1) < 0.5)
    )
    raw = valid & built_context & (signals >= thresholds["minimum_signals"])
    labels, _ = ndimage.label(raw, structure=np.ones((3, 3), dtype="uint8"))
    sizes = np.bincount(labels.ravel())
    keep = sizes >= int(thresholds["minimum_component_pixels"])
    keep[0] = False
    candidate = keep[labels]
    return {
        "grid": grid,
        "aoi_mask": aoi_mask,
        "valid": valid,
        "candidate": candidate,
        "labels": np.where(candidate, labels, 0).astype("int32"),
        "sizes": sizes,
        "deltas": deltas,
        "clear": clear,
        "built_context": built_context,
    }


def _zonal_counts(geometries, spectral: dict) -> dict[str, np.ndarray]:
    """Per-geometry valid/candidate pixel counts and mean deltas.

    Footprints are burned ``all_touched`` into an id raster; where neighbouring
    footprints share a pixel the later one wins, and footprints left with no pixel
    fall back to the pixel under their representative point.
    """
    from rasterio.features import rasterize
    from rasterio.transform import rowcol

    count = len(geometries)
    shape = spectral["valid"].shape
    transform = spectral["grid"]["transform"]
    ids = np.zeros(shape, dtype="int32")
    if count:
        ids = rasterize(
            [(geometry, index + 1) for index, geometry in enumerate(geometries)],
            out_shape=shape,
            transform=transform,
            fill=0,
            dtype="int32",
            all_touched=True,
        )
    flat_ids = ids.ravel()
    valid = spectral["valid"].ravel()
    candidate = spectral["candidate"].ravel()
    length = count + 1
    valid_counts = np.bincount(flat_ids, weights=valid, minlength=length)
    candidate_counts = np.bincount(flat_ids, weights=candidate & valid, minlength=length)
    sums = {
        name: np.bincount(
            flat_ids, weights=np.where(valid, np.nan_to_num(values.ravel()), 0), minlength=length
        )
        for name, values in spectral["deltas"].items()
    }
    present = np.bincount(flat_ids, minlength=length) > 0
    for index, geometry in enumerate(geometries, start=1):
        if present[index]:
            continue
        point = geometry.representative_point()
        row, col = rowcol(transform, point.x, point.y)
        if 0 <= row < shape[0] and 0 <= col < shape[1] and spectral["valid"][row, col]:
            valid_counts[index] = 1
            candidate_counts[index] = float(spectral["candidate"][row, col])
            for name, values in spectral["deltas"].items():
                sums[name][index] = float(np.nan_to_num(values[row, col]))
    with np.errstate(invalid="ignore", divide="ignore"):
        means = {name: sums[name] / valid_counts for name in sums}
    return {
        "valid": valid_counts[1:].astype(int),
        "candidate": candidate_counts[1:].astype(int),
        **{f"mean_delta_{name}": values[1:] for name, values in means.items()},
    }


def _assign_neighborhoods(frame, neighborhoods, name_field: str):
    """Representative-point-in-polygon attribution; points outside → ``unknown``."""
    import geopandas as gpd

    points = gpd.GeoDataFrame(
        {"_row": range(len(frame))},
        geometry=frame.geometry.representative_point(),
        crs=frame.crs,
    )
    joined = gpd.sjoin(
        points, neighborhoods[[name_field, "geometry"]], how="left", predicate="within"
    ).sort_values("_row")
    joined = joined[~joined["_row"].duplicated(keep="first")]
    return joined[name_field].fillna("unknown").astype(str).to_numpy()


def analyze(root: Path, config: dict) -> dict:
    import geopandas as gpd
    import pandas as pd
    from rasterio.features import rasterize, shapes
    from shapely.geometry import shape

    osm = config["osm"]
    sentinel = config["sentinel2"]
    metric_crs = config["metric_crs"]
    name_field = config["neighborhood_name_field"]
    aoi = aoi_wgs84(root, config)

    # --- OSM footprints -----------------------------------------------------
    snapshot_dir = root / osm["snapshot_directory"]
    # Snapshot files are named after the OSM timestamp keys written by acquire.
    timestamp_keys = {"post": "post_event", "current": "current"}
    paths = {
        role: snapshot_dir / f"buildings_{timestamp_keys[role]}.geojson" for role in ROLES
    }
    documents = {
        role: load_snapshot(paths[role], osm["timestamps"][timestamp_keys[role]])
        for role in ROLES
    }
    frames, audits = {}, {}
    for role in ROLES:
        frames[role], audits[role] = prepare_frame(documents[role], aoi, metric_crs)
        if frames[role].empty:
            raise ValueError(f"No buildings selected in the {role} snapshot")
    before, after = frames["post"], frames["current"]
    rows = match_buildings(
        list(before.geometry), list(after.geometry), osm["minimum_iou"], osm["unchanged_iou"]
    )
    records = []
    for number, row in enumerate(rows):
        i, j = row["before_index"], row["after_index"]
        status = row["status"]
        boundary = bool(
            (i is not None and before.iloc[i]["boundary_review"])
            or (j is not None and after.iloc[j]["boundary_review"])
        )
        repair = bool(
            (i is not None and before.iloc[i]["repair_review"])
            or (j is not None and after.iloc[j]["repair_review"])
        )
        if boundary or repair:
            status = "uncertain"
        records.append(
            {
                "unit_id": f"recon-{number:06d}",
                "layer": "osm_footprint",
                "osm_match_status": status,
                "post_osm_id": None if i is None else before.iloc[i]["source_id"],
                "current_osm_id": None if j is None else after.iloc[j]["source_id"],
                "iou": row["iou"],
                "candidate_count": row["candidate_count"],
                "boundary_review": boundary,
                "repair_review": repair,
                "post_area_m2": None if i is None else float(before.geometry.iloc[i].area),
                "current_area_m2": None if j is None else float(after.geometry.iloc[j].area),
                "geometry": row["geometry"],
            }
        )
    units = gpd.GeoDataFrame(records, geometry="geometry", crs=metric_crs)
    units["footprint_area_m2"] = units.geometry.area

    # --- Spectral change ----------------------------------------------------
    spectral = _spectral_change(root, config)
    zonal = _zonal_counts(list(units.geometry), spectral)
    support = sentinel["thresholds"]["footprint_support_fraction"]
    classified = [
        classify_footprint(status, int(valid), int(candidate), support)
        for status, valid, candidate in zip(
            units["osm_match_status"], zonal["valid"], zonal["candidate"], strict=True
        )
    ]
    units["reconstruction_class"] = [item[0] for item in classified]
    units["evidence"] = [item[1] for item in classified]
    units["spectral_change_fraction"] = [item[2] for item in classified]
    units["clear_pixels"] = zonal["valid"]
    units["spectral_change_pixels"] = zonal["candidate"]
    for name in ("ndvi", "ndbi", "bsi"):
        units[f"mean_delta_{name}"] = np.where(
            zonal["valid"] > 0, zonal[f"mean_delta_{name}"], np.nan
        )
    units["direction_hint"] = [
        direction_hint(a, b, c)
        for a, b, c in zip(
            units["mean_delta_ndvi"], units["mean_delta_ndbi"], units["mean_delta_bsi"], strict=True
        )
    ]

    # Spectral components not touching any removed/new/modified OSM unit.
    transform = spectral["grid"]["transform"]
    change_units = units[
        units["reconstruction_class"].isin(
            ["removed_candidate", "new_candidate", "modified_candidate"]
        )
    ]
    change_tree = change_units.sindex
    component_rows = []
    for geometry_mapping, value in shapes(
        spectral["labels"], mask=spectral["candidate"], transform=transform
    ):
        geometry = shape(geometry_mapping)
        if len(change_tree.query(geometry, predicate="intersects")):
            continue
        component_rows.append({"label": int(value), "geometry": geometry})
    components = gpd.GeoDataFrame(component_rows, geometry="geometry", crs=metric_crs)
    if not components.empty:
        components = components.dissolve(by="label", as_index=False)
        zonal_components = _zonal_counts(list(components.geometry), spectral)
        components["unit_id"] = [f"spectral-{n:05d}" for n in range(1, len(components) + 1)]
        components["layer"] = "spectral_component"
        components["osm_match_status"] = None
        components["reconstruction_class"] = "spectral_only_change"
        components["evidence"] = "spectral_only"
        components["footprint_area_m2"] = components.geometry.area
        components["clear_pixels"] = zonal_components["valid"]
        components["spectral_change_pixels"] = zonal_components["candidate"]
        components["spectral_change_fraction"] = np.where(
            zonal_components["valid"] > 0,
            zonal_components["candidate"] / np.maximum(zonal_components["valid"], 1),
            np.nan,
        )
        for name in ("ndvi", "ndbi", "bsi"):
            components[f"mean_delta_{name}"] = zonal_components[f"mean_delta_{name}"]
        components["direction_hint"] = [
            direction_hint(a, b, c)
            for a, b, c in zip(
                components["mean_delta_ndvi"],
                components["mean_delta_ndbi"],
                components["mean_delta_bsi"],
                strict=True,
            )
        ]
        components = components.drop(columns=["label"])

    # --- Neighbourhood attribution and indicators ----------------------------
    neighborhoods = gpd.read_file(root / config["aoi"]).to_crs(metric_crs)
    if name_field not in neighborhoods:
        raise ValueError(f"Missing neighborhood field: {name_field}")
    units["neighborhood"] = _assign_neighborhoods(units, neighborhoods, name_field)
    if not components.empty:
        components["neighborhood"] = _assign_neighborhoods(components, neighborhoods, name_field)

    zone = rasterize(
        [(geometry, index + 1) for index, geometry in enumerate(neighborhoods.geometry)],
        out_shape=spectral["valid"].shape,
        transform=transform,
        fill=0,
        dtype="int32",
    )
    pixel_area = float(sentinel["resolution_metres"]) ** 2
    valid_by_zone = np.bincount(zone.ravel(), weights=spectral["valid"].ravel(),
                                minlength=len(neighborhoods) + 1)
    change_by_zone = np.bincount(
        zone.ravel(), weights=(spectral["candidate"] & spectral["valid"]).ravel(),
        minlength=len(neighborhoods) + 1,
    )
    spectral_by_neighborhood = {
        str(name): {
            "valid_m2": float(valid_by_zone[index + 1] * pixel_area),
            "change_m2": float(change_by_zone[index + 1] * pixel_area),
        }
        for index, name in enumerate(neighborhoods[name_field])
    }
    neighborhood_table = pd.DataFrame(
        {
            "neighborhood": neighborhoods[name_field].astype(str),
            "area_km2": neighborhoods.geometry.area / 1_000_000,
        }
    )
    if (units["neighborhood"] == "unknown").any():
        neighborhood_table = pd.concat(
            [neighborhood_table, pd.DataFrame([{"neighborhood": "unknown", "area_km2": 0.0}])],
            ignore_index=True,
        )
    indicators = neighborhood_indicators(units, spectral_by_neighborhood, neighborhood_table)

    # --- Map output (change only; persistent footprints are counted, not drawn) --
    map_columns = [
        "unit_id", "layer", "reconstruction_class", "evidence", "osm_match_status",
        "post_osm_id", "current_osm_id", "iou", "candidate_count", "boundary_review",
        "repair_review", "footprint_area_m2", "post_area_m2", "current_area_m2",
        "clear_pixels", "spectral_change_pixels", "spectral_change_fraction",
        "mean_delta_ndvi", "mean_delta_ndbi", "mean_delta_bsi", "direction_hint",
        "neighborhood", "geometry",
    ]
    drawn = units[units["reconstruction_class"] != "persistent"]
    parts = [drawn]
    if not components.empty:
        parts.append(components)
    change_map = gpd.GeoDataFrame(
        pd.concat(parts, ignore_index=True), geometry="geometry", crs=metric_crs
    ).reindex(columns=map_columns)
    change_map["class_label_tr"] = change_map["reconstruction_class"].map(CLASS_LABELS_TR)
    assert_no_damage_fields(change_map.columns)

    # --- Separate EMSR648 co-occurrence context (never joined into the map) ---
    damage = gpd.read_file(root / config["copernicus"]).to_crs(metric_crs)
    damage = damage[damage.geometry.notna() & ~damage.geometry.is_empty]
    context_source = gpd.GeoDataFrame(
        pd.concat([units, components], ignore_index=True) if not components.empty else units,
        geometry="geometry",
        crs=metric_crs,
    )[["unit_id", "reconstruction_class", "geometry"]]
    pairs = gpd.sjoin(
        context_source, damage[["damage_grade", "geometry"]], how="inner", predicate="intersects"
    )
    context = (
        pairs.drop_duplicates(["unit_id", "damage_grade"])
        .groupby(["reconstruction_class", "damage_grade"])
        .size()
        .rename("units_intersecting")
        .reset_index()
    )
    totals = context_source.groupby("reconstruction_class").size()
    context["units_in_class"] = context["reconstruction_class"].map(totals)
    context["interpretation"] = "spatial co-occurrence only; not a damage label or accuracy"

    # --- Write and round-trip ------------------------------------------------
    output = root / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    map_path = output / "reconstruction_change_map.geojson"
    parquet_path = output / "reconstruction_change_map.parquet"
    indicators_path = output / "neighborhood_reconstruction_indicators.csv"
    context_path = output / "reconstruction_vs_emsr648_context.csv"
    # The GeoJSON is a committed map layer: round float attributes to keep it small.
    # Geometry coordinates are untouched; the GeoParquet keeps full precision.
    web_map = change_map.to_crs(4326)
    float_columns = web_map.select_dtypes("float").columns
    web_map[float_columns] = web_map[float_columns].round(4)
    web_map.to_file(map_path, driver="GeoJSON")
    change_map.to_parquet(parquet_path, index=False)
    indicators.to_csv(indicators_path, index=False)
    context.to_csv(context_path, index=False)

    reopened = gpd.read_file(map_path)
    reopened_parquet = gpd.read_parquet(parquet_path)
    reopened_indicators = pd.read_csv(indicators_path)
    if len(reopened) != len(change_map) or len(reopened_parquet) != len(change_map):
        raise ValueError("Reconstruction map roundtrip count mismatch")
    if not reopened.geometry.is_valid.all():
        raise ValueError("Reconstruction map contains invalid geometry")
    if len(reopened_indicators) != len(indicators):
        raise ValueError("Indicator roundtrip count mismatch")
    # Conservation: every footprint of each snapshot is represented exactly once.
    if int(units["post_area_m2"].notna().sum()) != len(before):
        raise ValueError("Post-event footprints not conserved")
    if int(units["current_area_m2"].notna().sum()) != len(after):
        raise ValueError("Current footprints not conserved")
    if int(indicators["osm_buildings_2023"].sum()) != len(before):
        raise ValueError("Neighbourhood indicators do not conserve 2023 footprints")

    valid_pixels = int(spectral["valid"].sum())
    aoi_pixels = int(spectral["aoi_mask"].sum())
    scenes = sentinel["scenes"]
    post_time = datetime.fromisoformat(scenes["post"]["datetime"].replace("Z", "+00:00"))
    current_time = datetime.fromisoformat(scenes["current"]["datetime"].replace("Z", "+00:00"))
    class_counts = units["reconstruction_class"].value_counts().to_dict()
    evidence_counts = (
        units.groupby(["reconstruction_class", "evidence"]).size().rename("count").reset_index()
    )
    report = {
        "status": "completed_reconstruction_screening",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "period": {
            "osm_post_event": osm["timestamps"]["post_event"],
            "osm_current": osm["timestamps"]["current"],
            "sentinel2_post": scenes["post"]["datetime"],
            "sentinel2_current": scenes["current"]["datetime"],
            "sentinel2_gap_days": round((current_time - post_time).total_seconds() / 86400, 2),
        },
        "osm": {
            "post_event": audits["post"],
            "current": audits["current"],
            "reconstruction_class_counts": {k: int(v) for k, v in class_counts.items()},
            "evidence_counts": json.loads(evidence_counts.to_json(orient="records")),
            "net_footprint_count_change": len(after) - len(before),
            "post_footprint_area_m2": float(before.geometry.area.sum()),
            "current_footprint_area_m2": float(after.geometry.area.sum()),
            "threshold_sensitivity_raw_matching": {
                str(threshold): pd.Series(
                    [
                        OSM_TO_RECONSTRUCTION[r["status"]]
                        for r in match_buildings(
                            list(before.geometry), list(after.geometry), threshold,
                            osm["unchanged_iou"],
                        )
                    ]
                ).value_counts().to_dict()
                for threshold in (0.3, 0.5, 0.7)
            },
        },
        "sentinel2": {
            "scenes": scenes,
            "reflectance_correction": "DN * scale + offset (offset -0.1 for baseline >= 04.00)",
            "indices": ["NDVI", "NDBI", "BSI"],
            "thresholds": sentinel["thresholds"],
            "post_invalid_aoi_percent": 100
            * float((spectral["aoi_mask"] & ~spectral["clear"]["post"]).sum()) / aoi_pixels,
            "current_invalid_aoi_percent": 100
            * float((spectral["aoi_mask"] & ~spectral["clear"]["current"]).sum()) / aoi_pixels,
            "joint_valid_aoi_percent": 100 * valid_pixels / aoi_pixels,
            "candidate_pixels": int(spectral["candidate"].sum()),
            "candidate_area_m2": float(spectral["candidate"].sum()) * pixel_area,
            "candidate_fraction_of_valid": float(spectral["candidate"].sum()) / valid_pixels,
            "spectral_only_components": len(components),
        },
        "map_features": len(change_map),
        "map_feature_counts": change_map["reconstruction_class"].value_counts().to_dict(),
        "neighborhoods_reported": len(indicators),
        "units_without_neighborhood": int((units["neighborhood"] == "unknown").sum()),
        "emsr648_context_rows": len(context),
        "damage_fields_in_change_outputs": False,
        "inputs_sha256": {
            **{
                paths[role].relative_to(root).as_posix(): sha256(paths[role]) for role in ROLES
            },
            config["aoi"]: sha256(root / config["aoi"]),
            config["copernicus"]: sha256(root / config["copernicus"]),
            **{
                f"{role}/{band}.tif": sha256_file(
                    root / sentinel["local_raster_directory"] / role
                    / scenes[role]["item_id"] / f"{band}.tif"
                )
                for role in ROLES
                for band in BANDS
            },
        },
        "outputs_sha256": {
            path.name: sha256(path)
            for path in (map_path, parquet_path, indicators_path, context_path)
        },
        "roundtrip_valid": True,
        "limitations": [
            "OSM snapshots record mapping state; a footprint absent in 2026 may be an "
            "editing correction, and a new one may be a pre-existing building mapped late.",
            f"The 2026 OSM snapshot ({osm['timestamps']['current'][:10]}) and the 2026 "
            f"Sentinel-2 scene ({sentinel['scenes']['current']['datetime'][:10]}) are not "
            "simultaneous; buildings changed between the two dates are mislabelled.",
            "Sentinel-2 pixels are 10 m; most footprints cover only a few mixed pixels.",
            "Spectral change still includes phenology, soil-moisture and snow differences "
            "between the two scenes; persistent footprints are spectrally supported too, "
            "so spectral support is corroboration, not proof.",
            *(
                [sentinel["current_scene_selection"]]
                if sentinel.get("current_scene_selection")
                else []
            ),
            "Spectral thresholds are screening rules, not calibrated against field data.",
            "Change classes are never damage classes; EMSR648 co-occurrence is descriptive.",
        ],
    }
    report_dir = root / config["report_directory"]
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "reconstruction_validation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, default=str) + "\n", encoding="utf-8"
    )
    return report
