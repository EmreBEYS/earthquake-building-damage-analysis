"""Dated footprint comparison; mapping changes are never inferred demolition labels."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from shapely import STRtree, make_valid
from shapely.geometry import MultiPolygon

STATUSES = ("unchanged", "geometry_changed", "newly_mapped", "unmatched", "uncertain")


def repair_polygon(geometry):
    """Retain polygon parts only; collapsed features are rejected and counted."""
    if geometry is None or geometry.is_empty:
        return None
    fixed = make_valid(geometry)
    if fixed.geom_type == "GeometryCollection":
        parts = []
        for part in fixed.geoms:
            if part.geom_type == "Polygon":
                parts.append(part)
            elif part.geom_type == "MultiPolygon":
                parts.extend(part.geoms)
        fixed = MultiPolygon(parts)
    if fixed.geom_type not in {"Polygon", "MultiPolygon"} or fixed.is_empty:
        return None
    return fixed if fixed.area > 0 else None


def match_buildings(before, after, minimum_iou=0.5, unchanged_iou=0.9):
    """Match metric polygon sequences with conservative one-to-one overlap components.

    Any positive-area split/merge or competing candidate is uncertain. No greedy
    assignment hides ambiguity. Non-overlapping additions mean newly MAPPED only.
    The returned rows conserve every input feature exactly once on each side.
    """
    if not 0 < minimum_iou < unchanged_iou <= 1:
        raise ValueError("Require 0 < minimum_iou < unchanged_iou <= 1")
    for geometry in [*before, *after]:
        if repair_polygon(geometry) is None or not geometry.is_valid:
            raise ValueError("Inputs must be repaired valid polygons in a shared metric CRS")
    tree = STRtree(after)
    edges, reverse = {}, {}
    for i, left in enumerate(before):
        candidates = []
        for j in tree.query(left, predicate="intersects"):
            j = int(j)
            intersection = left.intersection(after[j]).area
            if intersection <= 0:
                continue
            iou = intersection / (left.area + after[j].area - intersection)
            candidates.append((j, float(iou)))
            reverse.setdefault(j, []).append(i)
        edges[i] = sorted(candidates, key=lambda x: (-x[1], x[0]))
    rows, consumed = [], set()
    for i, candidates in edges.items():
        j, iou = candidates[0] if candidates else (None, 0.0)
        unique = len(candidates) == 1 and len(reverse.get(j, [])) == 1
        accepted = unique and iou >= minimum_iou
        status = "unmatched" if not candidates else "uncertain"
        if accepted:
            status = "unchanged" if iou >= unchanged_iou else "geometry_changed"
            consumed.add(j)
        rows.append({"before_index": i, "after_index": j if accepted else None,
                     "best_after_candidate": j, "iou": iou, "status": status,
                     "candidate_count": len(candidates), "geometry": before[i]})
    for j, geometry in enumerate(after):
        if j not in consumed:
            rows.append({"before_index": None, "after_index": j,
                         "best_after_candidate": None, "iou": None,
                         "status": "uncertain" if j in reverse else "newly_mapped",
                         "candidate_count": len(reverse.get(j, [])), "geometry": geometry})
    return rows


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_snapshot(path, expected_timestamp):
    """Validate actual ohsome per-feature snapshot metadata, not filenames/edit dates."""
    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if document.get("type") != "FeatureCollection" or not document.get("features"):
        raise ValueError(f"Empty/non-GeoJSON snapshot: {path}")
    ids = []
    for feature in document["features"]:
        props = feature["properties"]
        if props.get("@snapshotTimestamp") != expected_timestamp:
            raise ValueError(f"Snapshot date differs from requested date: {path}")
        identifier = props.get("@osmId", feature.get("id"))
        if identifier is None:
            raise ValueError("Missing stable source feature identifier")
        ids.append(str(identifier))
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source feature identifiers")
    return document


def acquire_snapshots(root, config):
    """Immutable real OSM history extracts with request and payload hashes."""
    import httpx

    scope = json.loads((root / "configs/datasets.json").read_text())["geoboundaries"]
    boundary_path = root / config["district_boundaries"]
    if not boundary_path.exists():
        response = httpx.get(scope["download_url"], follow_redirects=True, timeout=45)
        response.raise_for_status()
        if hashlib.sha256(response.content).hexdigest() != scope["sha256"]:
            raise ValueError("Pinned district boundary checksum mismatch")
        boundary_path.parent.mkdir(parents=True, exist_ok=True)
        boundary_path.write_bytes(response.content)
    if sha256(boundary_path) != scope["sha256"]:
        raise ValueError("Pinned district boundary checksum mismatch")
    directory = root / "data/external/building_change"
    directory.mkdir(parents=True, exist_ok=True)
    for year, timestamp in config["timestamps"].items():
        target = directory / f"buildings_{year}.geojson"
        if target.exists():
            load_snapshot(target, timestamp)
            continue
        request = {"bboxes": ",".join(map(str, config["bbox"])), "time": timestamp,
                   "filter": "building=* and geometry:polygon", "properties": "tags,metadata",
                   "clipGeometry": "false"}
        response = httpx.post(config["endpoint"], data=request, timeout=45)
        response.raise_for_status()
        temporary = target.with_suffix(".part")
        temporary.write_bytes(response.content)
        load_snapshot(temporary, timestamp)
        temporary.replace(target)
        target.with_suffix(".source.json").write_text(json.dumps({
            "endpoint": config["endpoint"], "request": request,
            "retrieved_at": datetime.now(timezone.utc).isoformat(), "sha256": sha256(target),
            "license": "ODbL 1.0; © OpenStreetMap contributors",
            "semantics": "OSM mapping state, not physical observation date",
        }, indent=2), encoding="utf-8")


def prepare_frame(document, aoi, metric_crs):
    import geopandas as gpd

    frame = gpd.GeoDataFrame.from_features(document["features"], crs="EPSG:4326")
    source_count = len(frame)
    frame["source_id"] = [str(f["properties"].get("@osmId", f.get("id")))
                          for f in document["features"]]
    frame["repair_review"] = ~frame.geometry.is_valid
    invalid = int(frame["repair_review"].sum())
    frame.geometry = frame.geometry.map(repair_polygon)
    collapsed = int(frame.geometry.isna().sum())
    frame = frame[frame.geometry.notna()].copy()
    # Select full footprints, never clip them into artificial changes at AOI edges.
    frame = frame[frame.geometry.intersects(aoi)].to_crs(metric_crs).reset_index(drop=True)
    frame["boundary_review"] = ~frame.geometry.covered_by(
        gpd.GeoSeries([aoi], crs=4326).to_crs(metric_crs).iloc[0])
    return frame, {"source_count": source_count, "invalid_before_repair": invalid,
                   "collapsed_excluded": collapsed, "selected": len(frame)}


def run_analysis(root, config):
    import geopandas as gpd
    import pandas as pd
    from importlib.metadata import version
    from shapely.geometry import box

    snapshots = [root / f"data/external/building_change/buildings_{year}.geojson"
                 for year in (2022, 2023)]
    documents = [load_snapshot(p, config["timestamps"][str(year)])
                 for p, year in zip(snapshots, (2022, 2023))]
    scope = json.loads((root / "configs/datasets.json").read_text())["geoboundaries"]
    district_path = root / config["district_boundaries"]
    if sha256(district_path) != scope["sha256"]:
        raise ValueError("District boundary checksum mismatch")
    districts = gpd.read_file(district_path)
    districts = districts[districts["shapeID"].isin(scope["selected_shape_ids"])]
    if len(districts) != 2:
        raise ValueError("Expected pinned Battalgazi and Yesilyurt district boundaries")
    aoi = districts.to_crs(4326).geometry.union_all().intersection(box(*config["bbox"]))
    neighborhoods = gpd.read_file(root / config["neighborhoods"])
    before, before_audit = prepare_frame(documents[0], aoi, config["metric_crs"])
    after, after_audit = prepare_frame(documents[1], aoi, config["metric_crs"])
    if before.empty or after.empty:
        raise ValueError("No buildings selected in one of the dated snapshots")
    if before_audit["collapsed_excluded"] or after_audit["collapsed_excluded"]:
        raise ValueError("Collapsed source geometries require review before change classification")
    rows = match_buildings(list(before.geometry), list(after.geometry),
                           config["minimum_iou"], config["unchanged_iou"])
    for n, row in enumerate(rows):
        i, j = row["before_index"], row["after_index"]
        row["change_id"] = f"change-{n:06d}"
        row["before_id"] = None if i is None else before.iloc[i]["source_id"]
        row["after_id"] = None if j is None else after.iloc[j]["source_id"]
        row["boundary_review"] = bool((i is not None and before.iloc[i]["boundary_review"])
                                      or (j is not None and after.iloc[j]["boundary_review"]))
        row["repair_review"] = bool((i is not None and before.iloc[i]["repair_review"])
                                    or (j is not None and after.iloc[j]["repair_review"]))
        if row["boundary_review"] or row["repair_review"]:
            row["status"] = "uncertain"
    changes = gpd.GeoDataFrame(rows, geometry="geometry", crs=config["metric_crs"])
    boundaries = neighborhoods.to_crs(changes.crs)
    # Maximum intersection attribution, deterministic tie handling and unknown bucket.
    name_field = config["neighborhood_name_field"]
    if name_field not in boundaries:
        raise ValueError(f"Missing neighborhood field: {name_field}")
    changes["neighborhood"] = "unknown"
    for index, row in changes.iterrows():
        candidates = boundaries[boundaries.geometry.intersects(row.geometry)]
        overlaps = [(float(g.intersection(row.geometry).area), str(name))
                    for g, name in zip(candidates.geometry, candidates[name_field])]
        overlaps = sorted((a, name) for a, name in overlaps if a > 0)
        if overlaps and (len(overlaps) == 1 or overlaps[-1][0] > overlaps[-2][0] * 1.01):
            changes.loc[index, "neighborhood"] = overlaps[-1][1]
    damage = gpd.read_file(root / config["copernicus"]).to_crs(changes.crs)
    tree = STRtree(list(damage.geometry))
    comparisons = []
    for _, row in changes.iterrows():
        for j in tree.query(row.geometry, predicate="intersects"):
            observed = damage.iloc[int(j)]
            area = row.geometry.intersection(observed.geometry).area
            if area > 0:
                comparisons.append({"change_id": row.change_id, "status": row.status,
                                    "damage_grade": observed["damage_grade"],
                                    "intersection_area_m2": area,
                                    "change_area_fraction": area / row.geometry.area,
                                    "copernicus_index": int(j)})
    output = root / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    changes.to_crs(4326).to_file(output / "building_change_2022_2023.geojson", driver="GeoJSON")
    changes.to_parquet(output / "building_change_2022_2023.parquet", index=False)
    for frame, year in ((before, 2022), (after, 2023)):
        frame[["source_id", "geometry"]].to_crs(4326).to_file(
            output / f"buildings_{year}.geojson", driver="GeoJSON")
    summary = changes.groupby(["neighborhood", "status"]).size().unstack(fill_value=0)
    summary = summary.reindex(columns=STATUSES, fill_value=0)
    summary["analysis_units"] = summary.sum(axis=1)
    summary.to_csv(output / "neighborhood_change_summary.csv")
    pd.DataFrame(comparisons, columns=["change_id", "status", "damage_grade",
                                     "intersection_area_m2", "change_area_fraction",
                                     "copernicus_index"]).to_csv(
        output / "copernicus_overlap_comparison.csv", index=False)
    reopened = gpd.read_parquet(output / "building_change_2022_2023.parquet")
    geojson = gpd.read_file(output / "building_change_2022_2023.geojson")
    if len(reopened) != len(changes) or len(geojson) != len(changes):
        raise ValueError("Output roundtrip count mismatch")
    if not reopened.geometry.is_valid.all() or not geojson.geometry.is_valid.all():
        raise ValueError("Invalid output geometry")
    return {"status": "completed_mapping_change_only", "before": before_audit,
            "after": after_audit, "counts": changes.status.value_counts().to_dict(),
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "inputs_sha256": {str(p.relative_to(root)): sha256(p) for p in
                              [*snapshots, district_path, root / config["neighborhoods"],
                               root / config["copernicus"]]},
            "outputs_sha256": {p.name: sha256(p) for p in output.iterdir() if p.is_file()},
            "versions": {p: version(p) for p in
                         ("geopandas", "shapely", "pyarrow", "pyproj", "pandas")},
            "config": config, "comparison_pairs": len(comparisons),
            "district_boundary_sha256": sha256(district_path),
            "source_semantics": "Mapping changes between December 31 snapshots; not earthquake damage",
            "summary_total": int(summary.analysis_units.sum()),
            "roundtrip_valid": True,
            "threshold_sensitivity_raw_matching": {
                str(threshold): pd.Series([r["status"] for r in match_buildings(
                    list(before.geometry), list(after.geometry), threshold,
                    config["unchanged_iou"])]).value_counts().to_dict()
                for threshold in (0.3, 0.5, 0.7)
            },
            "limitations": "Not causal earthquake attribution; no demolition or construction labels. "
            "Copernicus overlap pairs are spatial associations, not accuracy measurements."}
