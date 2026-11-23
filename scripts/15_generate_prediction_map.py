"""Generate the Sprint 00-17 building-level prediction GeoJSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from earthquake_damage.sprint_00_17 import generate_prediction_map


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    keyword_arguments = {}
    if arguments.project_root is not None:
        keyword_arguments["project_root"] = arguments.project_root
    if arguments.config is not None:
        keyword_arguments["config_path"] = arguments.config
    if arguments.output is not None:
        keyword_arguments["output_path"] = arguments.output
    print(
        json.dumps(
            generate_prediction_map(**keyword_arguments),
            ensure_ascii=False,
            indent=2,
        )
    )
