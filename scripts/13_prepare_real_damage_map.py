"""Prepare and validate Sprint 00-15 real damage map artifacts."""

from __future__ import annotations

import json

from earthquake_damage.sprint_00_15 import prepare_real_damage_map


if __name__ == "__main__":
    print(json.dumps(prepare_real_damage_map(), ensure_ascii=False, indent=2))
