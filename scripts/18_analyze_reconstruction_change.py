"""Sprint 00-19: acquire 2023/2026 evidence and build the reconstruction change map."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from earthquake_damage.reconstruction_change_analysis import (  # noqa: E402
    acquire,
    analyze,
    screen_current_scenes,
)

CONFIG = ROOT / "configs/sprint_00_19.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("screen", "acquire", "analyze", "all"))
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    report_dir = ROOT / config["report_directory"]
    report_dir.mkdir(parents=True, exist_ok=True)
    try:
        if args.command == "screen":
            result = screen_current_scenes(ROOT, config)
            (report_dir / "scene_screening.json").write_text(
                json.dumps({"aoi_scl_invalid_percent": result}, indent=2) + "\n",
                encoding="utf-8",
            )
            print(json.dumps(result, indent=2))
            return 0
        if args.command in {"acquire", "all"}:
            print(json.dumps(acquire(ROOT, config), indent=2, default=str))
        if args.command in {"analyze", "all"}:
            report = analyze(ROOT, config)
            print(json.dumps({k: report[k] for k in ("status", "osm", "map_features")},
                             indent=2, default=str, ensure_ascii=False))
    except Exception as error:  # record blocking evidence instead of a silent failure
        blocked = {"status": "blocked", "error_type": type(error).__name__,
                   "reason": str(error), "results_generated": False}
        (report_dir / "blocked.json").write_text(json.dumps(blocked, indent=2) + "\n",
                                                 encoding="utf-8")
        print(json.dumps(blocked, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
