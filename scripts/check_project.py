"""Offline smoke checks for repository layout and dataset metadata."""

from __future__ import annotations

import csv
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "data" / "inventory.csv"
CONFIG = ROOT / "configs" / "datasets.json"

REQUIRED_PATHS = (
    "README.md",
    "pyproject.toml",
    "uv.lock",
    "data/raw/.gitkeep",
    "data/external/.gitkeep",
    "data/interim/.gitkeep",
    "data/processed/.gitkeep",
    "data/inventory.csv",
    "docs/data-sources.md",
    "docs/sprints/sprint-00-01.md",
)
REQUIRED_COLUMNS = {
    "dataset_id",
    "status",
    "provider",
    "coverage",
    "temporal_coverage",
    "accessed_on",
    "license_or_terms",
    "redistribution",
    "crs",
    "local_path",
    "sha256",
    "source_url",
    "validation_notes",
}
ALLOWED_STATUSES = {
    "validated_local_only",
    "catalogued_local_only",
    "planned",
    "pending_verified_download",
    "excluded_private",
    "excluded_proprietary",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def inventory_rows() -> list[dict[str, str]]:
    with INVENTORY.open(encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        missing = REQUIRED_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"inventory missing columns: {sorted(missing)}")
        return list(reader)


def validate_inventory(rows: list[dict[str, str]]) -> list[str]:
    errors: list[str] = []
    identifiers: set[str] = set()
    for number, row in enumerate(rows, start=2):
        dataset_id = row["dataset_id"]
        if not dataset_id or dataset_id in identifiers:
            errors.append(f"row {number}: blank or duplicate dataset_id {dataset_id!r}")
        identifiers.add(dataset_id)
        if row["status"] not in ALLOWED_STATUSES:
            errors.append(f"row {number}: unsupported status {row['status']!r}")
        if not row["license_or_terms"]:
            errors.append(f"row {number}: license_or_terms is required")
        if row["source_url"]:
            parsed = urlparse(row["source_url"])
            if parsed.scheme != "https" or not parsed.netloc:
                errors.append(f"row {number}: source_url must be an HTTPS URL")
        if row["local_path"]:
            path = PurePosixPath(row["local_path"])
            if path.is_absolute() or ".." in path.parts or path.parts[0] != "data":
                errors.append(f"row {number}: unsafe local_path {row['local_path']!r}")
        if row["sha256"] and not SHA256_RE.fullmatch(row["sha256"]):
            errors.append(f"row {number}: sha256 must contain 64 lowercase hex characters")
        if row["status"] in {"planned", "pending_verified_download"} and row["sha256"]:
            errors.append(f"row {number}: pending/planned data must not claim a checksum")
    return errors


def validate_config() -> list[str]:
    errors: list[str] = []
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    bbox = config.get("aoi_bbox_wgs84")
    if not (
        isinstance(bbox, list)
        and len(bbox) == 4
        and all(isinstance(value, (int, float)) for value in bbox)
        and bbox[0] < bbox[2]
        and bbox[1] < bbox[3]
    ):
        errors.append("aoi_bbox_wgs84 must be [west, south, east, north]")
    for key in ("copernicus_ems", "geoboundaries", "sentinel_2"):
        if key not in config:
            errors.append(f"datasets config missing {key!r}")
    return errors


def tracked_payloads() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "data/raw", "data/external", "data/interim", "data/processed"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [path for path in result.stdout.splitlines() if not path.endswith("/.gitkeep")]


def main() -> None:
    errors = [f"required path missing: {path}" for path in REQUIRED_PATHS if not (ROOT / path).exists()]
    rows = inventory_rows()
    errors.extend(validate_inventory(rows))
    errors.extend(validate_config())
    errors.extend(f"dataset payload is tracked: {path}" for path in tracked_payloads())
    summary = {
        "ok": not errors,
        "inventory_records": len(rows),
        "local_payloads_expected": sum(
            row["status"] in {"validated_local_only", "catalogued_local_only"} for row in rows
        ),
        "errors": errors,
    }
    print(json.dumps(summary, indent=2))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
