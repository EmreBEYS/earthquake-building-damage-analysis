"""Dated OpenStreetMap building snapshots from Overpass attic queries.

Shared by Sprint 00-18 (2022/2023) and Sprint 00-19 (2023/2026). Overpass is often
overloaded, so a bbox is split into tiles that are cached one by one: an interrupted
download resumes from the first missing tile instead of starting over.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

LICENSE = "ODbL 1.0; © OpenStreetMap contributors"
SEMANTICS = "OSM mapping state at the timestamp, not a physical survey date"


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def overpass_query(bounds: tuple[float, float, float, float], timestamp: str) -> str:
    """Overpass QL for closed building ways as they existed at ``timestamp`` (attic data)."""
    west, south, east, north = bounds
    return (
        f'[out:json][timeout:900][maxsize:1073741824][date:"{timestamp}"];'
        f"way[building]({south:.6f},{west:.6f},{north:.6f},{east:.6f});"
        "out tags geom meta;"
    )


def tile_bounds(bounds: tuple[float, float, float, float], per_axis: int) -> list[tuple]:
    """Split (west, south, east, north) into ``per_axis``² edge-sharing tiles."""
    if per_axis < 1:
        raise ValueError("per_axis must be >= 1")
    west, south, east, north = bounds
    xs = np.linspace(west, east, per_axis + 1)
    ys = np.linspace(south, north, per_axis + 1)
    return [
        (float(xs[i]), float(ys[j]), float(xs[i + 1]), float(ys[j + 1]))
        for j in range(per_axis)
        for i in range(per_axis)
    ]


def merge_overpass_payloads(payloads: list[dict]) -> dict:
    """Merge tiled responses; a way crossing tiles is kept once (identical at one date)."""
    elements, seen, bases = [], set(), set()
    for payload in payloads:
        bases.add(payload.get("osm3s", {}).get("timestamp_osm_base"))
        for element in payload.get("elements", []):
            key = (element.get("type"), element.get("id"))
            if key in seen:
                continue
            seen.add(key)
            elements.append(element)
    bases.discard(None)
    return {"osm3s": {"timestamp_osm_base": max(bases) if bases else None}, "elements": elements}


def overpass_to_geojson(payload: dict, timestamp: str) -> dict:
    """Convert an Overpass ``out geom`` response into a dated building FeatureCollection.

    Only closed ways with at least four vertices become polygons; open ways are
    counted and dropped. ``@snapshotTimestamp`` records the requested attic date so
    the Sprint 00-18 snapshot validator can enforce date consistency.
    """
    features, open_ways = [], 0
    for element in payload.get("elements", []):
        if element.get("type") != "way" or "geometry" not in element:
            continue
        ring = [[point["lon"], point["lat"]] for point in element["geometry"]]
        if len(ring) < 4 or ring[0] != ring[-1]:
            open_ways += 1
            continue
        features.append(
            {
                "type": "Feature",
                "id": f"way/{element['id']}",
                "properties": {
                    "@osmId": f"way/{element['id']}",
                    "@snapshotTimestamp": timestamp,
                    "@version": element.get("version"),
                    "@lastEdit": element.get("timestamp"),
                    "building": element.get("tags", {}).get("building"),
                },
                "geometry": {"type": "Polygon", "coordinates": [ring]},
            }
        )
    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "snapshot_timestamp": timestamp,
            "osm_base": payload.get("osm3s", {}).get("timestamp_osm_base"),
            "open_ways_dropped": open_ways,
        },
    }


def download_snapshot(
    target: Path,
    bounds: tuple[float, float, float, float],
    timestamp: str,
    endpoints: list[str],
    tiles_per_axis: int,
    tile_prefix: str,
    validate,
) -> dict:
    """Download (or resume) one dated snapshot and write it with a provenance sidecar.

    ``validate(path, timestamp)`` must raise if the merged file is not a valid snapshot.
    """
    import time

    import httpx

    target = Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    tiles = tile_bounds(bounds, tiles_per_axis)
    endpoints_used: set[str] = set()
    if not target.exists():
        tile_dir = target.parent / "tiles"
        tile_dir.mkdir(exist_ok=True)
        payloads = []
        for number, tile in enumerate(tiles):
            cache = tile_dir / f"{tile_prefix}_{number:02d}.json"
            if cache.exists():  # resumable: finished tiles are never re-requested
                payloads.append(json.loads(cache.read_text(encoding="utf-8")))
                continue
            last_error: Exception | None = None
            for attempt, endpoint in enumerate(endpoints * 3):
                try:
                    response = httpx.post(
                        endpoint,
                        data={"data": overpass_query(tile, timestamp)},
                        timeout=960,
                        headers={"User-Agent": "earthquake-damage-research/0.1 (reproducible)"},
                    )
                    response.raise_for_status()
                    payload = response.json()
                    if "remark" in payload and "error" in payload["remark"].lower():
                        raise ValueError(payload["remark"])
                    endpoints_used.add(endpoint)
                    break
                except (httpx.HTTPError, ValueError) as error:
                    last_error = error
                    time.sleep(min(120, 10 * 2**attempt))
            else:
                raise RuntimeError(f"Overpass tile {number} failed: {last_error}")
            cache.write_text(json.dumps(payload), encoding="utf-8")
            payloads.append(payload)
            print(
                f"{tile_prefix} tile {number + 1}/{len(tiles)}: "
                f"{len(payload.get('elements', []))} elements",
                flush=True,
            )
        document = overpass_to_geojson(merge_overpass_payloads(payloads), timestamp)
        temporary = target.with_suffix(".part")
        temporary.write_text(json.dumps(document), encoding="utf-8")
        validate(temporary, timestamp)
        temporary.replace(target)
    document = validate(target, timestamp)
    record = {
        "role": tile_prefix,
        "endpoints": sorted(endpoints_used),
        "query_template": overpass_query(bounds, timestamp),
        "tiles": len(tiles),
        "retrieved_at": datetime.now(UTC).isoformat(),
        "features": len(document["features"]),
        "osm_base": document.get("metadata", {}).get("osm_base"),
        "open_ways_dropped": document.get("metadata", {}).get("open_ways_dropped"),
        "sha256": _sha256(target),
        "license": LICENSE,
        "semantics": SEMANTICS,
    }
    source = target.with_suffix(".source.json")
    if not source.exists():
        source.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record
