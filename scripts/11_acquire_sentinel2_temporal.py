"""Plan, acquire and validate keyless Sentinel-2 temporal GeoTIFFs."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "sentinel2_temporal.json"
PLAN_PATH = ROOT / "data" / "manifests" / "sentinel2_temporal_plan.json"
LOCAL_MANIFEST = (
    ROOT / "data" / "external" / "sentinel_2" / "geotiff" / "acquisition_manifest.json"
)


def load_config(path: Path = CONFIG_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def search_parameters(config: dict, scene: dict) -> dict[str, str]:
    date = scene["date"]
    return {
        "collections": config["collection"],
        "bbox": ",".join(str(value) for value in config["aoi_bbox_wgs84"]),
        "datetime": f"{date}T00:00:00Z/{date}T23:59:59Z",
        "limit": "100",
    }


def search_url(config: dict, scene: dict) -> str:
    query = urllib.parse.urlencode(search_parameters(config, scene))
    return f"{config['stac_url'].rstrip('/')}/search?{query}"


def build_plan(config: dict) -> dict:
    output = config["output"]
    return {
        "sprint": "00-13",
        "schema_version": config["schema_version"],
        "provider": config["provider"],
        "stac_url": config["stac_url"],
        "collection": config["collection"],
        "aoi_bbox_wgs84": config["aoi_bbox_wgs84"],
        "target_mgrs": config["target_mgrs"],
        "output": output,
        "authentication": "not_required",
        "scenes": [
            {
                **scene,
                "output_path": (
                    f"{output['destination']}/{scene['label']}_{output['asset']}.tif"
                ),
                "search_url": search_url(config, scene),
                "search_sha256": sha256_bytes(search_url(config, scene).encode()),
            }
            for scene in config["scenes"]
        ],
        "attribution": config["attribution"],
        "interpretation": (
            "Sentinel-2 imagery supports temporal remote-sensing review; it is not an official "
            "building-damage record and does not geolocate official records to buildings."
        ),
    }


def write_plan(config: dict, path: Path = PLAN_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(build_plan(config), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def fetch_catalog(config: dict, scene: dict) -> dict:
    request = urllib.request.Request(
        search_url(config, scene),
        headers={"Accept": "application/geo+json", "User-Agent": "earthquake-damage-research/1"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:  # nosec: configured HTTPS
            return json.load(response)
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"Earth Search failed with HTTP {error.code}: {detail}") from error


def _matches_mgrs(item: dict, target: dict) -> bool:
    properties = item.get("properties", {})
    structured = (
        properties.get("mgrs:utm_zone") == target["utm_zone"]
        and properties.get("mgrs:latitude_band") == target["latitude_band"]
        and properties.get("mgrs:grid_square") == target["grid_square"]
    )
    tile_values = (
        item.get("id", ""),
        str(properties.get("s2:mgrs_tile", "")),
        str(properties.get("mgrs:tile", "")),
    )
    return structured or any(target["tile"] in value.upper() for value in tile_values)


def select_item(config: dict, catalog: dict) -> dict:
    asset = config["output"]["asset"]
    candidates = [
        item
        for item in catalog.get("features", [])
        if _matches_mgrs(item, config["target_mgrs"]) and asset in item.get("assets", {})
    ]
    if not candidates:
        raise RuntimeError(
            f"No {config['target_mgrs']['tile']} item with the {asset!r} asset was found"
        )
    return min(
        candidates,
        key=lambda item: (
            float(item.get("properties", {}).get("eo:cloud_cover", 100.0)),
            item.get("id", ""),
        ),
    )


def scene_path(config: dict, scene: dict) -> Path:
    output = config["output"]
    return ROOT / output["destination"] / f"{scene['label']}_{output['asset']}.tif"


def acquire_scene(config: dict, scene: dict) -> dict:
    destination = scene_path(config, scene)
    if destination.exists():
        return {
            "label": scene["label"],
            "path": destination.relative_to(ROOT).as_posix(),
            "bytes": destination.stat().st_size,
            "sha256": sha256_file(destination),
            "reused_existing_file": True,
        }

    item = select_item(config, fetch_catalog(config, scene))
    asset = item["assets"][config["output"]["asset"]]
    href = str(asset["href"])
    if not href.startswith("https://"):
        raise RuntimeError(f"Refusing non-HTTPS asset URL: {href}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(href, headers={"User-Agent": "earthquake-damage-research/1"})
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent, suffix=".part", delete=False
        ) as stream:
            temporary = Path(stream.name)
            with urllib.request.urlopen(request, timeout=300) as response:  # nosec: selected HTTPS
                while chunk := response.read(1024 * 1024):
                    stream.write(chunk)
    except Exception:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        raise
    assert temporary is not None
    try:
        with temporary.open("rb") as stream:
            if stream.read(4) not in (b"II*\x00", b"MM\x00*"):
                raise RuntimeError(f"Downloaded asset for {scene['label']} is not a TIFF")
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "label": scene["label"],
        "item_id": item["id"],
        "acquisition_datetime_utc": item.get("properties", {}).get("datetime"),
        "cloud_cover_percent": item.get("properties", {}).get("eo:cloud_cover"),
        "asset": config["output"]["asset"],
        "source_href": href,
        "path": destination.relative_to(ROOT).as_posix(),
        "bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
        "reused_existing_file": False,
    }


def _read_tiff_tags(path: Path, wanted: set[int]) -> dict[int, tuple[int | float, ...]]:
    """Read the small set of classic TIFF tags needed for validation."""
    type_layouts = {3: (2, "H"), 4: (4, "I"), 12: (8, "d")}
    with path.open("rb") as stream:
        byte_order = stream.read(2)
        if byte_order == b"II":
            prefix = "<"
        elif byte_order == b"MM":
            prefix = ">"
        else:
            raise ValueError(f"not a TIFF: {path}")
        if struct.unpack(f"{prefix}H", stream.read(2))[0] != 42:
            raise ValueError(f"unsupported TIFF header: {path}")
        directory_offset = struct.unpack(f"{prefix}I", stream.read(4))[0]
        stream.seek(directory_offset)
        entry_count = struct.unpack(f"{prefix}H", stream.read(2))[0]
        entries = [stream.read(12) for _ in range(entry_count)]

        result: dict[int, tuple[int | float, ...]] = {}
        for entry in entries:
            tag, value_type, count = struct.unpack(f"{prefix}HHI", entry[:8])
            if tag not in wanted or value_type not in type_layouts:
                continue
            size, code = type_layouts[value_type]
            byte_count = size * count
            if byte_count <= 4:
                payload = entry[8 : 8 + byte_count]
            else:
                value_offset = struct.unpack(f"{prefix}I", entry[8:12])[0]
                stream.seek(value_offset)
                payload = stream.read(byte_count)
            result[tag] = struct.unpack(f"{prefix}{count}{code}", payload)
    return result


def validate_geotiff(path: Path, config: dict) -> dict:
    output = config["output"]
    tags = _read_tiff_tags(path, {256, 257, 277, 33550, 34735})
    width = int(tags[256][0])
    height = int(tags[257][0])
    if (width, height) != (output["width"], output["height"]):
        raise ValueError(f"unexpected raster size for {path}: {(width, height)}")
    samples = int(tags[277][0])
    if samples != len(output["bands"]):
        raise ValueError(f"unexpected band count for {path}: {samples}")
    geo_keys = tuple(int(value) for value in tags[34735])
    expected_epsg = int(output["crs"].split(":")[-1])
    if expected_epsg not in geo_keys:
        raise ValueError(f"GeoTIFF does not declare {output['crs']}: {path}")
    pixel_scale = tuple(float(value) for value in tags[33550])
    if len(pixel_scale) < 2 or any(
        abs(value - output["pixel_size_metres"]) > 0.001 for value in pixel_scale[:2]
    ):
        raise ValueError(f"unexpected pixel scale for {path}: {pixel_scale}")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
        "width": width,
        "height": height,
        "bands": output["bands"],
        "crs": output["crs"],
        "pixel_size_metres": output["pixel_size_metres"],
        "valid": True,
    }


def selected_scenes(config: dict, labels: list[str]) -> list[dict]:
    scenes = config["scenes"]
    if not labels:
        return scenes
    by_label = {scene["label"]: scene for scene in scenes}
    missing = sorted(set(labels) - set(by_label))
    if missing:
        raise ValueError(f"unknown scene labels: {missing}")
    return [by_label[label] for label in labels]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("plan", help="write the reviewable keyless acquisition plan")
    download = commands.add_parser("download", help="download selected public GeoTIFFs")
    download.add_argument("--scene", action="append", default=[])
    validate = commands.add_parser("validate", help="validate downloaded GeoTIFFs")
    validate.add_argument("--scene", action="append", default=[])
    args = parser.parse_args()
    config = load_config()
    write_plan(config)
    scenes = selected_scenes(config, getattr(args, "scene", []))
    if args.command == "plan":
        print(PLAN_PATH)
        return
    if args.command == "download":
        downloads = [acquire_scene(config, scene) for scene in scenes]
        checks = [validate_geotiff(ROOT / item["path"], config) for item in downloads]
        manifest = {
            "sprint": "00-13",
            "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
            "authentication": "not_required",
            "downloads": downloads,
            "validation": checks,
            "attribution": config["attribution"],
        }
        LOCAL_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return
    checks = []
    for scene in scenes:
        path = scene_path(config, scene)
        if not path.is_file():
            raise FileNotFoundError(f"GeoTIFF is missing: {path}")
        checks.append(validate_geotiff(path, config))
    print(json.dumps({"valid": True, "files": checks}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
