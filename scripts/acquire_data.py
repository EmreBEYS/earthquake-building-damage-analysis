"""Acquire immutable public inputs and catalogue metadata without downloading imagery."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs" / "datasets.json"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def install_immutable(source: Path, destination: Path, expected_sha256: str | None) -> Path:
    source_hash = sha256(source)
    if expected_sha256 and source_hash != expected_sha256:
        raise ValueError(f"checksum mismatch for {source}: {source_hash}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if sha256(destination) != source_hash:
            raise FileExistsError(f"refusing to overwrite different raw file: {destination}")
        return destination
    shutil.copyfile(source, destination)
    if sha256(destination) != source_hash:
        destination.unlink(missing_ok=True)
        raise OSError(f"copy verification failed: {destination}")
    return destination


def download_immutable(url: str, destination: Path, expected_sha256: str | None) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if not expected_sha256 or sha256(destination) == expected_sha256:
            return destination
        raise FileExistsError(f"refusing to overwrite different source file: {destination}")
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".part", delete=False) as tmp:
        temporary = Path(tmp.name)
        with urllib.request.urlopen(url, timeout=120) as response:  # nosec: pinned public URL
            shutil.copyfileobj(response, tmp)
    try:
        return install_immutable(temporary, destination, expected_sha256)
    finally:
        temporary.unlink(missing_ok=True)


def copy_cems(source: Path, config: dict) -> Path:
    item = config["copernicus_ems"]
    destination = ROOT / item["destination"] / item["filename"]
    return install_immutable(source.resolve(), destination, item["sha256"])


def download_boundaries(config: dict) -> Path:
    item = config["geoboundaries"]
    destination = ROOT / item["destination"] / item["filename"]
    return download_immutable(item["download_url"], destination, item["sha256"])


def query_sentinel(config: dict) -> list[Path]:
    item = config["sentinel_2"]
    destination = ROOT / item["destination"]
    destination.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for label, interval in item["windows"].items():
        payload = {
            "collections": [item["collection"]],
            "bbox": config["aoi_bbox_wgs84"],
            "datetime": interval,
            "query": {"eo:cloud_cover": {"lte": item["max_cloud_cover"]}},
            "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
            "limit": item["limit"],
        }
        request = urllib.request.Request(
            item["stac_search_url"],
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "earthquake-dataset/0.1"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=120) as response:  # nosec: official endpoint
            result = json.load(response)
        compact = {
            "type": result.get("type"),
            "context": result.get("context"),
            "numberMatched": result.get("numberMatched"),
            "numberReturned": result.get("numberReturned"),
            "query": payload,
            "features": [
                {
                    "type": feature.get("type"),
                    "stac_version": feature.get("stac_version"),
                    "id": feature.get("id"),
                    "collection": feature.get("collection"),
                    "bbox": feature.get("bbox"),
                    "geometry": feature.get("geometry"),
                    "properties": feature.get("properties"),
                    "links": [
                        link
                        for link in feature.get("links", [])
                        if link.get("rel") in {"self", "collection", "license"}
                    ],
                }
                for feature in result.get("features", [])
            ],
        }
        output = destination / f"{label}.json"
        payload_bytes = (json.dumps(compact, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        with tempfile.NamedTemporaryFile(dir=destination, suffix=".part", delete=False) as tmp:
            temporary = Path(tmp.name)
            tmp.write(payload_bytes)
        try:
            outputs.append(install_immutable(temporary, output, expected_sha256=None))
        finally:
            temporary.unlink(missing_ok=True)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    copy_parser = commands.add_parser("copy-cems", help="copy a trusted local EMSR648 ZIP")
    copy_parser.add_argument("--source", required=True, type=Path)
    commands.add_parser("download-boundaries", help="download pinned Türkiye ADM2 GeoJSON")
    commands.add_parser("query-sentinel", help="store compact Sentinel-2 STAC metadata only")
    args = parser.parse_args()
    config = load_config()
    if args.command == "copy-cems":
        print(copy_cems(args.source, config))
    elif args.command == "download-boundaries":
        print(download_boundaries(config))
    elif args.command == "query-sentinel":
        for path in query_sentinel(config):
            print(path)


if __name__ == "__main__":
    main()
