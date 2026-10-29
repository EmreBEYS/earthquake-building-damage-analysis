"""Acquire current OSM geometries for the committed high-coverage relation IDs."""

from __future__ import annotations

import csv
import json
import time
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
EXACT_MATCH = ROOT / "reports" / "sprint_00-10" / "v3_official_osm_exact_match.csv"
HIGH_COVERAGE = ROOT / "reports" / "sprint_00-10" / "v3_high_coverage_analysis.csv"
OUTPUT = ROOT / "data" / "external" / "osm" / "aoi05_high_coverage_neighborhoods.geojson"
USER_AGENT = "earthquake-building-damage-analysis/00-12 (academic research dashboard)"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def main() -> None:
    high_names = {row["mahalle"] for row in read_rows(HIGH_COVERAGE)}
    selected = [row for row in read_rows(EXACT_MATCH) if row["mahalle"] in high_names]
    expected_by_id = {row["id"].split("/")[-1]: row for row in selected}
    features: list[dict] = []

    relation_ids = sorted(expected_by_id, key=int)
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
            records = json.load(response)
        for record in records:
            relation_id = str(record["osm_id"])
            expected = expected_by_id[relation_id]
            features.append(
                {
                    "type": "Feature",
                    "id": f"relation/{relation_id}",
                    "properties": {
                        "id": f"relation/{relation_id}",
                        "name": record.get("namedetails", {}).get("name", expected["mahalle"]),
                        "display_name": record.get("display_name"),
                        "source": "OpenStreetMap contributors via Nominatim lookup",
                    },
                    "geometry": record["geojson"],
                }
            )
        if start + 40 < len(relation_ids):
            time.sleep(1.1)

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
