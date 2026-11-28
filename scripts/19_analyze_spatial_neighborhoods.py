"""Run Sprint 00-20: neighbourhood damage density, hot spots and comparison table."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from earthquake_damage.spatial_analysis import run  # noqa: E402


def main() -> int:
    # Windows consoles default to a legacy code page; Turkish labels and arrows need UTF-8.
    sys.stdout.reconfigure(encoding="utf-8")
    config = json.loads((ROOT / "configs/sprint_00_20.json").read_text(encoding="utf-8"))
    report_dir = ROOT / config["report_directory"]
    report_dir.mkdir(parents=True, exist_ok=True)
    blocked = report_dir / "blocked.json"
    try:
        report = run(ROOT, config)
    except Exception as error:  # record the failure instead of pretending results exist
        payload = {"status": "blocked", "error_type": type(error).__name__,
                   "reason": str(error), "results_generated": False}
        blocked.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2))
        return 1
    blocked.unlink(missing_ok=True)
    print(json.dumps({k: report[k] for k in ("status", "neighborhoods", "global_morans_i",
                                             "source_rank_correlations", "grid")},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
