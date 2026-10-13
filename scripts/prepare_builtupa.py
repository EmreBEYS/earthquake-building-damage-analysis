from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
import sys
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path


ARCHIVE = Path(sys.argv[1])
OUTPUT = Path(sys.argv[2])
STEM = "EMSR648_AOI05_GRA_PRODUCT_builtUpA_r1_v1"
EARTH_RADIUS_M = 6_371_008.8

LABELS = {
    "No visible damage": ("no_visible_damage", 0, 0),
    "Possibly damaged": ("possibly_damaged", 1, 1),
    "Damaged": ("damaged", 2, 1),
    "Destroyed": ("destroyed", 3, 1),
}


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_dbf(payload: bytes) -> tuple[list[str], list[dict[str, str]]]:
    record_count = struct.unpack("<I", payload[4:8])[0]
    header_length = struct.unpack("<H", payload[8:10])[0]
    record_length = struct.unpack("<H", payload[10:12])[0]
    fields: list[tuple[str, int]] = []
    offset = 32
    while offset < header_length - 1:
        descriptor = payload[offset : offset + 32]
        if descriptor[:1] == b"\r":
            break
        name = descriptor[:11].split(b"\0", 1)[0].decode("ascii")
        fields.append((name, descriptor[16]))
        offset += 32
    rows = []
    offset = header_length
    for _ in range(record_count):
        record = payload[offset : offset + record_length]
        offset += record_length
        if record[:1] == b"*":
            continue
        position = 1
        row = {}
        for name, width in fields:
            raw = record[position : position + width]
            position += width
            row[name] = raw.rstrip(b" \0").decode("utf-8", "strict")
        rows.append(row)
    return [name for name, _ in fields], rows


def read_polygon_shapes(payload: bytes) -> list[list[list[tuple[float, float]]]]:
    if len(payload) < 100 or struct.unpack(">i", payload[:4])[0] != 9994:
        raise ValueError("invalid shapefile header")
    if struct.unpack(">i", payload[24:28])[0] * 2 != len(payload):
        raise ValueError("shapefile length does not match its header")
    result = []
    offset = 100
    while offset < len(payload):
        size = struct.unpack(">i", payload[offset + 4 : offset + 8])[0] * 2
        body = payload[offset + 8 : offset + 8 + size]
        shape_type = struct.unpack("<i", body[:4])[0]
        if shape_type != 5:
            raise ValueError(f"unexpected builtUpA shape type: {shape_type}")
        part_count, point_count = struct.unpack("<2i", body[36:44])
        starts = list(struct.unpack(f"<{part_count}i", body[44 : 44 + part_count * 4]))
        point_offset = 44 + part_count * 4
        points = [
            struct.unpack("<2d", body[point_offset + index * 16 : point_offset + (index + 1) * 16])
            for index in range(point_count)
        ]
        starts.append(point_count)
        result.append([points[starts[i] : starts[i + 1]] for i in range(part_count)])
        offset += 8 + size
    return result


def signed_area(ring: list[tuple[float, float]]) -> float:
    return 0.5 * sum(
        ring[index][0] * ring[index + 1][1] - ring[index + 1][0] * ring[index][1]
        for index in range(len(ring) - 1)
    )


def group_rings(rings: list[list[tuple[float, float]]]):
    polygons: list[list[list[tuple[float, float]]]] = []
    for ring in rings:
        if len(ring) < 4 or ring[0] != ring[-1] or len(set(ring[:-1])) < 3:
            raise ValueError("invalid polygon ring in source shapefile")
        # ESRI Shapefile outer rings are clockwise; holes are counter-clockwise.
        if signed_area(ring) < 0 or not polygons:
            polygons.append([ring])
        else:
            polygons[-1].append(ring)
    return polygons


def geometry_mapping(polygons):
    coordinates = [
        [[[lon, lat] for lon, lat in ring] for ring in polygon]
        for polygon in polygons
    ]
    if len(coordinates) == 1:
        return {"type": "Polygon", "coordinates": coordinates[0]}
    return {"type": "MultiPolygon", "coordinates": coordinates}


def geodesic_ring_area_m2(ring: list[tuple[float, float]]) -> float:
    total = 0.0
    for index in range(len(ring) - 1):
        lon1, lat1 = map(math.radians, ring[index])
        lon2, lat2 = map(math.radians, ring[index + 1])
        total += (lon2 - lon1) * (2 + math.sin(lat1) + math.sin(lat2))
    return total * EARTH_RADIUS_M**2 / 2


def geometry_area_m2(polygons) -> float:
    return abs(sum(geodesic_ring_area_m2(ring) for polygon in polygons for ring in polygon))


def centroid_lon_lat(polygons) -> tuple[float, float]:
    weighted_x = weighted_y = total = 0.0
    all_points = []
    for polygon in polygons:
        for ring in polygon:
            all_points.extend(ring[:-1])
            cross_sum = 0.0
            cx_sum = cy_sum = 0.0
            for index in range(len(ring) - 1):
                x1, y1 = ring[index]
                x2, y2 = ring[index + 1]
                cross = x1 * y2 - x2 * y1
                cross_sum += cross
                cx_sum += (x1 + x2) * cross
                cy_sum += (y1 + y2) * cross
            if abs(cross_sum) > 1e-20:
                area = cross_sum / 2
                weighted_x += (cx_sum / (3 * cross_sum)) * area
                weighted_y += (cy_sum / (3 * cross_sum)) * area
                total += area
    if abs(total) > 1e-20:
        return weighted_x / total, weighted_y / total
    return (
        sum(point[0] for point in all_points) / len(all_points),
        sum(point[1] for point in all_points) / len(all_points),
    )


def wkt(polygons) -> str:
    def ring_text(ring):
        return ", ".join(f"{lon:.12f} {lat:.12f}" for lon, lat in ring)

    polygon_texts = [
        "(" + ", ".join(f"({ring_text(ring)})" for ring in polygon) + ")"
        for polygon in polygons
    ]
    if len(polygon_texts) == 1:
        return "POLYGON " + polygon_texts[0]
    return "MULTIPOLYGON (" + ", ".join(polygon_texts) + ")"


with zipfile.ZipFile(ARCHIVE) as archive:
    bad = archive.testzip()
    if bad:
        raise ValueError(f"archive CRC failure: {bad}")
    shp_payload = archive.read(f"{STEM}.shp")
    dbf_payload = archive.read(f"{STEM}.dbf")
    prj_payload = archive.read(f"{STEM}.prj")

fields, rows = read_dbf(dbf_payload)
shapes = read_polygon_shapes(shp_payload)
if len(rows) != len(shapes):
    raise ValueError(f"attribute/geometry count mismatch: {len(rows)} != {len(shapes)}")
if "WGS_1984" not in prj_payload.decode("utf-8-sig"):
    raise ValueError("builtUpA CRS is not WGS 84")

OUTPUT.mkdir(parents=True, exist_ok=True)
csv_path = OUTPUT / "EMSR648_AOI05_builtUpA_analysis.csv"
geojson_path = OUTPUT / "EMSR648_AOI05_builtUpA_analysis.geojson"
manifest_path = OUTPUT / "EMSR648_AOI05_builtUpA_manifest.json"

csv_fields = [
    "dataset_id",
    "source_dataset_id",
    "dataset_role",
    "building_id",
    "source_record_number",
    "building_use",
    "damage_class_original",
    "damage_class",
    "damage_label",
    "damage_binary",
    "detection_method",
    "original_source_id",
    "damage_source_id",
    "centroid_lon",
    "centroid_lat",
    "area_m2",
    "geometry_review_flag",
    "geometry_type",
    "geometry_wkt",
]
features = []
csv_rows = []
class_counts = Counter()
geometry_counts = Counter()
use_counts = Counter()
review_counts = Counter()
all_coordinates = []

for index, (source, rings) in enumerate(zip(rows, shapes), start=1):
    damage_original = source["damage_gra"]
    if damage_original not in LABELS:
        raise ValueError(f"unknown damage class: {damage_original!r}")
    damage_class, damage_label, damage_binary = LABELS[damage_original]
    polygons = group_rings(rings)
    geometry = geometry_mapping(polygons)
    centroid_lon, centroid_lat = centroid_lon_lat(polygons)
    area_m2 = geometry_area_m2(polygons)
    if area_m2 <= 0:
        raise ValueError(f"non-positive area at source record {index}")
    building_use = {
        "11-Residential Buildings": "residential",
        "12-Non-residential Buildings": "non_residential",
    }.get(source["obj_type"])
    if building_use is None:
        raise ValueError(f"unknown building class: {source['obj_type']!r}")
    building_id = f"EMSR648_AOI05_BLDG_{index:05d}"
    properties = {
        "dataset_id": "cems_emsr648_aoi05_builtupa_2023",
        "source_dataset_id": "cems_emsr648_aoi05_grading_vectors",
        "dataset_role": "damage_labels",
        "building_id": building_id,
        "source_record_number": index,
        "building_use": building_use,
        "damage_class_original": damage_original,
        "damage_class": damage_class,
        "damage_label": damage_label,
        "damage_binary": damage_binary,
        "detection_method": source["det_method"],
        "original_source_id": int(source["or_src_id"]),
        "damage_source_id": int(source["dmg_src_id"]),
        "centroid_lon": round(centroid_lon, 9),
        "centroid_lat": round(centroid_lat, 9),
        "area_m2": round(area_m2, 3),
        "geometry_review_flag": "tiny_under_1m2" if area_m2 < 1 else "none",
        "geometry_type": geometry["type"],
    }
    features.append({"type": "Feature", "properties": properties, "geometry": geometry})
    csv_rows.append({**properties, "geometry_wkt": wkt(polygons)})
    class_counts[damage_original] += 1
    geometry_counts[geometry["type"]] += 1
    use_counts[building_use] += 1
    review_counts[properties["geometry_review_flag"]] += 1
    for polygon in polygons:
        for ring in polygon:
            all_coordinates.extend(ring)

bbox = [
    min(point[0] for point in all_coordinates),
    min(point[1] for point in all_coordinates),
    max(point[0] for point in all_coordinates),
    max(point[1] for point in all_coordinates),
]
geojson = {
    "type": "FeatureCollection",
    "name": "EMSR648_AOI05_builtUpA_analysis",
    "bbox": bbox,
    "features": features,
}
geojson_path.write_text(json.dumps(geojson, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
with csv_path.open("w", encoding="utf-8", newline="") as stream:
    writer = csv.DictWriter(stream, fieldnames=csv_fields)
    writer.writeheader()
    writer.writerows(csv_rows)

manifest = {
    "schema_version": "1.0",
    "generated_on": date.today().isoformat(),
    "source": {
        "archive_filename": ARCHIVE.name,
        "archive_sha256": sha256_file(ARCHIVE),
        "layer": STEM,
        "shp_sha256": sha256_bytes(shp_payload),
        "dbf_sha256": sha256_bytes(dbf_payload),
        "crs": "EPSG:4326",
    },
    "outputs": {
        csv_path.name: {"sha256": sha256_file(csv_path), "rows": len(csv_rows)},
        geojson_path.name: {"sha256": sha256_file(geojson_path), "features": len(features)},
    },
    "summary": {
        "feature_count": len(features),
        "damage_class_counts": dict(class_counts),
        "building_use_counts": dict(use_counts),
        "geometry_type_counts": dict(geometry_counts),
        "geometry_review_flag_counts": dict(review_counts),
        "bbox_wgs84": bbox,
        "minimum_area_m2": min(row["area_m2"] for row in csv_rows),
        "maximum_area_m2": max(row["area_m2"] for row in csv_rows),
    },
    "derived_label_definition": {
        original: {
            "damage_class": values[0],
            "damage_label": values[1],
            "damage_binary": values[2],
        }
        for original, values in LABELS.items()
    },
    "cautions": [
        "damage_label is a project-defined ordinal code, not an official CEMS field",
        "damage_binary groups possibly damaged with observed damage",
        "CEMS grading is photo-interpretation and is not a structural safety certificate",
        "raw source data was not modified",
        "geometry_review_flag marks footprints under 1 m2 for review but does not remove them",
    ],
}
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, ensure_ascii=False, indent=2))
