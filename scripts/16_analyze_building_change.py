"""Acquire real dated OSM footprints and run Sprint 00-18."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from earthquake_damage.building_change_analysis import acquire_snapshots, run_analysis  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--acquire", action="store_true")
    args = parser.parse_args()
    config = json.loads((ROOT / "configs/sprint_00_18.json").read_text())
    report_dir = ROOT / "reports/sprint_00-18"
    report_dir.mkdir(parents=True, exist_ok=True)
    try:
        if args.acquire:
            acquire_snapshots(ROOT, config)
        report = run_analysis(ROOT, config)
    except Exception as error:
        report = {"status": "blocked", "error_type": type(error).__name__,
                  "reason": str(error), "config": config,
                  "results_generated": False}
        (report_dir / "validation_report.json").write_text(json.dumps(report, indent=2))
        print(json.dumps(report, indent=2))
        return 1
    (report_dir / "validation_report.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
