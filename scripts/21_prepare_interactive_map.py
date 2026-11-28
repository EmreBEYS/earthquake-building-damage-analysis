"""Prepare Sprint 00-22 building details for the interactive map's building panel."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from earthquake_damage.interactive_map import prepare  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    config = json.loads((ROOT / "configs/sprint_00_22.json").read_text(encoding="utf-8"))
    print(json.dumps(prepare(ROOT, config), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
