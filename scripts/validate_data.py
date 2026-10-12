"""Validate local raw/external geospatial sources without modifying them."""

from __future__ import annotations

import csv
import hashlib
import json
import struct
import zipfile
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "inventory.csv"
REPORT = ROOT / "data" / "validation_report.json"
LAYER_MANIFEST = ROOT / "data" / "manifests" / "EMSR648_AOI05_layers.csv"
SENTINEL_MANIFEST = ROOT / "data" / "manifests" / "sentinel2_candidates.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def coordinates(value):
    if (
        isinstance(value, list)
        and len(value) >= 2
        and isinstance(value[0], (int, float))
        and isinstance(value[1], (int, float))
    ):
        yield float(value[0]), float(value[1])
    elif isinstance(value, list):
        for child in value:
            yield from coordinates(child)


def geojson_summary(data: dict) -> dict:
    if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
        raise ValueError("not a GeoJSON FeatureCollection")
    geometry_types: Counter[str] = Counter()
    points: list[tuple[float, float]] = []
    for feature in data["features"]:
        geometry = feature.get("geometry")
        if not geometry or not geometry.get("type"):
            raise ValueError("feature has no geometry")
        geometry_types[geometry["type"]] += 1
        points.extend(coordinates(geometry.get("coordinates")))
    bbox = None
    if points:
        bbox = [
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        ]
    return {
        "feature_count": len(data["features"]),
        "geometry_types": dict(sorted(geometry_types.items())),
        "bbox": bbox,
    }


def shapefile_record_count(payload: bytes) -> int:
    if len(payload) < 100 or struct.unpack(">i", payload[0:4])[0] != 9994:
        raise ValueError("invalid shapefile header")
    declared_bytes = struct.unpack(">i", payload[24:28])[0] * 2
    if declared_bytes != len(payload):
        raise ValueError(f"shapefile size mismatch: header={declared_bytes}, actual={len(payload)}")
    offset = 100
    records = 0
    while offset < len(payload):
        if offset + 8 > len(payload):
            raise ValueError("truncated shapefile record header")
        content_bytes = struct.unpack(">i", payload[offset + 4 : offset + 8])[0] * 2
        offset += 8 + content_bytes
        records += 1
    if offset != len(payload):
        raise ValueError("truncated shapefile record")
    return records


def validate_cems(path: Path) -> tuple[dict, list[dict]]:
    layer_rows: list[dict] = []
    with zipfile.ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise ValueError(f"CRC failure: {bad_member}")
        names = archive.namelist()
        for name in names:
            member = Path(name)
            if member.is_absolute() or ".." in member.parts:
                raise ValueError(f"unsafe ZIP member: {name}")
        stems = {Path(name).stem for name in names if name.lower().endswith(".shp")}
        missing_companions = {
            stem: [
                extension
                for extension in (".dbf", ".shx", ".prj")
                if f"{stem}{extension}" not in names
            ]
            for stem in stems
        }
        missing_companions = {key: value for key, value in missing_companions.items() if value}
        if missing_companions:
            raise ValueError(f"incomplete shapefile sets: {missing_companions}")
        json_names = sorted(name for name in names if name.lower().endswith(".json"))
        for name in json_names:
            data = json.loads(archive.read(name).decode("utf-8-sig"))
            summary = geojson_summary(data)
            stem = Path(name).stem
            shape_records = shapefile_record_count(archive.read(f"{stem}.shp"))
            if shape_records != summary["feature_count"]:
                raise ValueError(
                    f"feature mismatch for {stem}: "
                    f"JSON={summary['feature_count']}, SHP={shape_records}"
                )
            prj = archive.read(f"{stem}.prj").decode("utf-8-sig")
            if "WGS_1984" not in prj:
                raise ValueError(f"unexpected CRS evidence for {stem}")
            layer_rows.append(
                {
                    "layer": stem,
                    "feature_count": summary["feature_count"],
                    "geometry_types": ";".join(
                        f"{key}:{value}" for key, value in summary["geometry_types"].items()
                    ),
                    "bbox_wgs84": json.dumps(summary["bbox"]),
                    "crs": "EPSG:4326 (from .prj WGS_1984)",
                }
            )
        return (
            {
                "zip_members": len(names),
                "zip_uncompressed_bytes": sum(info.file_size for info in archive.infolist()),
                "geojson_layers": len(json_names),
                "shapefile_sets": len(stems),
            },
            layer_rows,
        )


def validate_geojson(path: Path) -> dict:
    return geojson_summary(json.loads(path.read_text(encoding="utf-8-sig")))


def main() -> None:
    results: list[dict] = []
    layer_rows: list[dict] = []
    sentinel_rows: list[dict] = []
    with INVENTORY.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        if not row["local_path"]:
            results.append(
                {"dataset_id": row["dataset_id"], "status": row["status"], "checked": False}
            )
            continue
        path = ROOT / row["local_path"]
        result = {
            "dataset_id": row["dataset_id"],
            "path": row["local_path"],
            "exists": path.exists(),
            "checked": True,
        }
        if not path.exists():
            result["valid"] = False
            result["error"] = "file not found"
            results.append(result)
            continue
        try:
            result["bytes"] = path.stat().st_size
            result["sha256"] = sha256(path)
            if row["sha256"] and result["sha256"] != row["sha256"]:
                raise ValueError("checksum differs from inventory")
            if row["dataset_id"] == "cems_emsr648_aoi05_grading_vectors":
                result["content"], layer_rows = validate_cems(path)
            elif path.suffix.lower() in {".json", ".geojson"}:
                data = json.loads(path.read_text(encoding="utf-8-sig"))
                result["content"] = geojson_summary(data)
                if row["dataset_id"].startswith("sentinel2_l2a_"):
                    window = row["dataset_id"].removeprefix("sentinel2_l2a_")
                    for rank, feature in enumerate(data.get("features", [])[:5], start=1):
                        properties = feature.get("properties", {})
                        self_link = next(
                            (
                                link.get("href", "")
                                for link in feature.get("links", [])
                                if link.get("rel") == "self"
                            ),
                            "",
                        )
                        sentinel_rows.append(
                            {
                                "window": window,
                                "rank_by_catalog_response": rank,
                                "item_id": feature.get("id", ""),
                                "datetime_utc": properties.get("datetime", ""),
                                "platform": properties.get("platform", ""),
                                "mgrs_tile": properties.get("grid:code", ""),
                                "cloud_cover_percent": properties.get("eo:cloud_cover", ""),
                                "processing_version": properties.get("processing:version", ""),
                                "stac_item_url": self_link,
                            }
                        )
            result["valid"] = True
        except Exception as exc:  # report all validation failures together
            result["valid"] = False
            result["error"] = str(exc)
        results.append(result)
    REPORT.write_text(
        json.dumps(
            {"validated_on": date.today().isoformat(), "datasets": results}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    if layer_rows:
        LAYER_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with LAYER_MANIFEST.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=layer_rows[0].keys())
            writer.writeheader()
            writer.writerows(layer_rows)
    if sentinel_rows:
        SENTINEL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        with SENTINEL_MANIFEST.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=sentinel_rows[0].keys())
            writer.writeheader()
            writer.writerows(sentinel_rows)
    failures = [item for item in results if item.get("checked") and not item.get("valid")]
    checked = [item for item in results if item.get("checked")]
    print(
        json.dumps(
            {
                "checked": len(checked),
                "valid": len(checked) - len(failures),
                "metadata_only": len(results) - len(checked),
                "failed": failures,
            },
            indent=2,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
