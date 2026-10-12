"""Create the AOI-relevant district subset after source validation."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / "configs" / "datasets.json").read_text(encoding="utf-8"))


def main() -> None:
    report = json.loads((ROOT / "data" / "validation_report.json").read_text(encoding="utf-8"))
    source_id = "geoboundaries_tur_adm2_2021"
    source_result = next(item for item in report["datasets"] if item["dataset_id"] == source_id)
    if not source_result.get("valid"):
        raise RuntimeError("boundary source has not passed validation")
    config = CONFIG["geoboundaries"]
    source = ROOT / config["destination"] / config["filename"]
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    selected_ids = set(config["selected_shape_ids"])
    features = [
        feature
        for feature in data["features"]
        if feature.get("properties", {}).get("shapeID") in selected_ids
    ]
    found_ids = {feature["properties"]["shapeID"] for feature in features}
    if found_ids != selected_ids:
        raise ValueError(f"missing configured district IDs: {sorted(selected_ids - found_ids)}")
    output = ROOT / "data" / "interim" / "boundaries" / "malatya_battalgazi_yesilyurt.geojson"
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "type": "FeatureCollection",
        "name": "Malatya Battalgazi and Yesilyurt reference boundaries",
        "source_dataset": source_id,
        "features": features,
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
