"""Prepare Sprint 00-21 dashboard inputs: the neighbourhood → district table."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from earthquake_damage.ui.overview import prepare  # noqa: E402


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    config = json.loads((ROOT / "configs/sprint_00_21.json").read_text(encoding="utf-8"))
    print(json.dumps(prepare(ROOT, config), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
