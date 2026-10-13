from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path


root = Path(sys.argv[1])
csv_path = root / "EMSR648_AOI05_builtUpA_analysis.csv"
geojson_path = root / "EMSR648_AOI05_builtUpA_analysis.geojson"
manifest_path = root / "EMSR648_AOI05_builtUpA_manifest.json"


def sha256(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def orientation(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def proper_intersection(a, b, c, d):
    return orientation(a, b, c) * orientation(a, b, d) < 0 and orientation(c, d, a) * orientation(c, d, b) < 0


def rings(geometry):
    if geometry["type"] == "Polygon":
        yield from geometry["coordinates"]
    elif geometry["type"] == "MultiPolygon":
        for polygon in geometry["coordinates"]:
            yield from polygon
    else:
        raise ValueError(f"unexpected geometry: {geometry['type']}")


manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
geojson = json.loads(geojson_path.read_text(encoding="utf-8"))
with csv_path.open(encoding="utf-8", newline="") as stream:
    rows = list(csv.DictReader(stream))

errors = []
features = geojson.get("features", [])
if len(features) != 3619 or len(rows) != 3619:
    errors.append("unexpected record count")
if manifest["outputs"][csv_path.name]["sha256"] != sha256(csv_path):
    errors.append("CSV checksum mismatch")
if manifest["outputs"][geojson_path.name]["sha256"] != sha256(geojson_path):
    errors.append("GeoJSON checksum mismatch")

ids = [row["building_id"] for row in rows]
if len(set(ids)) != len(ids):
    errors.append("duplicate building_id")

self_intersections = 0
invalid_rings = 0
for feature in features:
    for ring in rings(feature["geometry"]):
        if len(ring) < 4 or ring[0] != ring[-1] or len({tuple(point) for point in ring[:-1]}) < 3:
            invalid_rings += 1
            continue
        segments = list(zip(ring[:-1], ring[1:]))
        for first in range(len(segments)):
            for second in range(first + 1, len(segments)):
                if second in {first, first + 1} or (first == 0 and second == len(segments) - 1):
                    continue
                if proper_intersection(*segments[first], *segments[second]):
                    self_intersections += 1

damage_counts = Counter(feature["properties"]["damage_class_original"] for feature in features)
review_counts = Counter(feature["properties"]["geometry_review_flag"] for feature in features)
if invalid_rings:
    errors.append(f"invalid rings: {invalid_rings}")
if self_intersections:
    errors.append(f"self intersections: {self_intersections}")

print(
    json.dumps(
        {
            "valid": not errors,
            "errors": errors,
            "csv_rows": len(rows),
            "geojson_features": len(features),
            "unique_building_ids": len(set(ids)),
            "invalid_rings": invalid_rings,
            "self_intersections": self_intersections,
            "damage_counts": dict(damage_counts),
            "review_flag_counts": dict(review_counts),
        },
        indent=2,
    )
)
raise SystemExit(bool(errors))
