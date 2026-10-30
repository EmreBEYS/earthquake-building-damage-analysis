"""Run the Sprint 00-14 geometry, feature and packaging pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from earthquake_damage.sprint_00_14 import DEFAULT_CONFIG, run_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser.parse_args()


def main() -> None:
    report = run_pipeline(parse_args().config)
    summary = {
        "valid": report["valid"],
        "metric_crs": report["metric_crs"],
        "building_count": report["sources"]["buildings"]["feature_count"],
        "neighborhood_count": report["sources"]["neighborhoods"]["feature_count"],
        "matched_buildings": report["checks"]["matched_building_count"],
        "unmatched_buildings": report["checks"]["building_unmatched_count"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
