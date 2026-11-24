"""Acquire aligned Sentinel-2 clips and run the Sprint 00-18 spectral screening."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from earthquake_damage.satellite_change_analysis import acquire_clips, analyze

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "configs/sprint_00_18_satellite.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("acquire", "analyze", "all"))
    args = parser.parse_args()
    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    if args.command in {"acquire", "all"}:
        acquire_clips(ROOT, config)
    if args.command in {"analyze", "all"}:
        print(json.dumps(analyze(ROOT, config), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
