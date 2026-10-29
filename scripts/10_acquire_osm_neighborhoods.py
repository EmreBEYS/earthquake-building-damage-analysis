"""Acquire current OSM geometries for all committed exact-match relation IDs."""

from __future__ import annotations

import csv
import argparse
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
EXACT_MATCH = ROOT / "reports" / "sprint_00-10" / "v3_official_osm_exact_match.csv"
ALIAS_CONFIG = ROOT / "configs" / "neighborhood_aliases.json"
OUTPUT = ROOT / "data" / "external" / "osm" / "aoi05_exact_match_neighborhoods.geojson"
USER_AGENT = "earthquake-building-damage-analysis/00-12 (academic research dashboard)"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--nominatim-response",
        type=Path,
        help="Import a saved Nominatim JSON response instead of querying the network.",
    )
    parser.add_argument(
        "--base-geojson",
        type=Path,
        help="Merge existing boundary features with an imported partial Nominatim response.",
    )
    return parser.parse_args()


def _feature_from_record(record: dict, expected: dict[str, str]) -> dict:
    relation_id = str(record["osm_id"])
    return {
        "type": "Feature",
        "id": f"relation/{relation_id}",
        "properties": {
            "id": f"relation/{relation_id}",
            "name": record.get("namedetails", {}).get("name")
            or record.get("name")
            or expected["mahalle"],
            "display_name": record.get("display_name"),
            "source": "OpenStreetMap contributors via Nominatim lookup",
        },
        "geometry": record["geojson"],
    }


def _base_features(path: Path | None) -> list[dict]:
    if path is None:
        return []
    document = json.loads(path.read_text(encoding="utf-8"))
    features: list[dict] = []
    for source in document.get("features", []):
        properties = source["properties"]
        relation_id = properties.get("id") or properties.get("neighborhood_id")
        name = properties.get("name") or properties.get("mahalle")
        features.append(
            {
                "type": "Feature",
                "id": relation_id,
                "properties": {
                    "id": relation_id,
                    "name": name,
                    "display_name": properties.get("display_name"),
                    "source": properties.get("source", "OpenStreetMap contributors"),
                },
                "geometry": source["geometry"],
            }
        )
    return features


def main() -> None:
    args = parse_args()
    selected = read_rows(EXACT_MATCH)
    expected_by_id = {row["id"].split("/")[-1]: row for row in selected}
    alias_config = json.loads(ALIAS_CONFIG.read_text(encoding="utf-8"))
    for alias in alias_config["aliases"]:
        relation_id = alias["target_relation_id"].split("/")[-1]
        expected_by_id.setdefault(relation_id, {"mahalle": alias["target_name"]})
    for boundary in alias_config["reference_only"]:
        relation_id = boundary["relation_id"].split("/")[-1]
        expected_by_id.setdefault(relation_id, {"mahalle": boundary["name"]})
    features = _base_features(args.base_geojson)

    relation_ids = sorted(expected_by_id, key=int)
    if args.nominatim_response:
        response_batches = [
            json.loads(args.nominatim_response.read_text(encoding="utf-8"))
        ]
    else:
        response_batches = []
        for start in range(0, len(relation_ids), 40):
            batch = relation_ids[start : start + 40]
            query = urlencode(
                {
                    "format": "jsonv2",
                    "osm_ids": ",".join(f"R{relation_id}" for relation_id in batch),
                    "polygon_geojson": 1,
                    "polygon_threshold": 0.000005,
                    "namedetails": 1,
                }
            )
            request = Request(
                f"https://nominatim.openstreetmap.org/lookup?{query}",
                headers={"User-Agent": USER_AGENT},
            )
            with urlopen(request, timeout=120) as response:  # nosec: fixed official OSM endpoint
                response_batches.append(json.load(response))
            if start + 40 < len(relation_ids):
                time.sleep(1.1)

    by_id = {feature["id"]: feature for feature in features}
    for records in response_batches:
        for record in records:
            relation_id = str(record["osm_id"])
            expected = expected_by_id.get(relation_id)
            if expected is None:
                raise ValueError(f"unexpected Nominatim relation id: {relation_id}")
            feature = _feature_from_record(record, expected)
            by_id[feature["id"]] = feature

    features = [by_id[f"relation/{relation_id}"] for relation_id in relation_ids if f"relation/{relation_id}" in by_id]

    found = {feature["id"].split("/")[-1] for feature in features}
    if found != set(relation_ids):
        missing = sorted(set(relation_ids) - found)
        raise RuntimeError(f"Nominatim did not return relation ids: {missing}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(OUTPUT)


if __name__ == "__main__":
    main()
