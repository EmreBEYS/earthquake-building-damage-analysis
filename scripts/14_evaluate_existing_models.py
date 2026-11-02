"""Run the Sprint 00-16 evaluation without overwriting saved models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from earthquake_damage.sprint_00_16 import evaluate_existing_models


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--output-root", type=Path, default=None)
    parser.add_argument("--config", type=Path, default=None)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    keyword_arguments = {}
    if arguments.project_root is not None:
        keyword_arguments["project_root"] = arguments.project_root
    if arguments.output_root is not None:
        keyword_arguments["output_root"] = arguments.output_root
    if arguments.config is not None:
        keyword_arguments["config_path"] = arguments.config
    result = evaluate_existing_models(**keyword_arguments)
    print(json.dumps(result, ensure_ascii=False, indent=2))

