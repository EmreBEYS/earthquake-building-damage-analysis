"""Pre-demo environment check for Windows and macOS (Sprint 00-24).

Run before a presentation:

    uv run python scripts/demo_check.py

It checks the Python version, required packages, committed dashboard inputs, optional
local-only data, whether the dashboard port is free and whether the app script compiles,
then prints the exact command to start the demo on this operating system. Exit code 0 means
the demo can run; optional items only warn.
"""

from __future__ import annotations

import argparse
import importlib
import json
import platform
import py_compile
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_PACKAGES = ("streamlit", "plotly", "pandas", "geopandas", "shapely", "pyogrio",
                     "matplotlib", "openpyxl", "sklearn", "scipy", "numpy")
REQUIRED_FILES = (
    "dashboard.py",
    ".streamlit/config.toml",
    "data/dashboard/sprint_00-12/aoi05_neighborhoods.geojson",
    "data/dashboard/sprint_00-12/copernicus_damage_polygons.geojson",
    "data/dashboard/sprint_00-15/official_neighborhood_statistics.csv",
    "data/dashboard/sprint_00-17/predicted_damage.geojson",
    "data/dashboard/sprint_00-19/reconstruction_change_map.geojson",
    "data/dashboard/sprint_00-20/neighborhood_spatial_analysis.geojson",
    "data/dashboard/sprint_00-21/neighborhood_districts.csv",
    "data/dashboard/sprint_00-22/building_details.csv",
    "reports/sprint_00-16/model_comparison.csv",
    "reports/sprint_00-23/spatial_confusion_matrix.json",
)
OPTIONAL_FILES = {
    "data/external/reconstruction/osm/buildings_post_event.geojson": "2023 OSM bina katmanı",
    "data/external/reconstruction/osm/buildings_current.geojson": "2026 OSM bina katmanı",
    "data/external/building_change/buildings_2022.geojson": "2022 OSM bina katmanı",
}


def port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", port)) != 0


def run_checks(root: Path = ROOT, port: int = 8501) -> dict:
    checks: list[dict] = []

    def record(name: str, ok: bool, detail: str = "", required: bool = True) -> None:
        checks.append({"check": name, "ok": ok, "required": required, "detail": detail})

    record("Python >= 3.11", sys.version_info >= (3, 11), platform.python_version())
    for package in REQUIRED_PACKAGES:
        try:
            module = importlib.import_module(package)
            record(f"paket: {package}", True, str(getattr(module, "__version__", "")))
        except Exception as error:  # report every missing package, not just the first
            record(f"paket: {package}", False, type(error).__name__)
    for relative in REQUIRED_FILES:
        record(f"dosya: {relative}", (root / relative).is_file())
    for relative, label in OPTIONAL_FILES.items():
        record(f"yerel veri: {label}", (root / relative).is_file(), relative, required=False)
    try:
        py_compile.compile(str(root / "dashboard.py"), doraise=True)
        record("dashboard.py derleniyor", True)
    except py_compile.PyCompileError as error:
        record("dashboard.py derleniyor", False, str(error))
    free = port_is_free(port)
    record(f"port {port} boş", free,
           "" if free else "başka bir uygulama kullanıyor; --server.port ile değiştirin",
           required=False)

    system = platform.system()
    command = "uv run python -m streamlit run dashboard.py"
    if not free:
        command += " --server.port 8502"
    ready = all(item["ok"] for item in checks if item["required"])
    return {"system": f"{system} {platform.release()} ({platform.machine()})",
            "python": platform.python_version(), "ready": ready, "start_command": command,
            "checks": checks}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print machine-readable output")
    parser.add_argument("--port", type=int, default=8501)
    args = parser.parse_args()
    result = run_checks(port=args.port)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Sistem: {result['system']} · Python {result['python']}")
        for item in result["checks"]:
            mark = "OK " if item["ok"] else ("HATA" if item["required"] else "UYARI")
            detail = f" — {item['detail']}" if item["detail"] else ""
            print(f"[{mark}] {item['check']}{detail}")
        print()
        print("Demo hazır." if result["ready"] else "Demo hazır DEĞİL: HATA satırlarını giderin.")
        print(f"Başlatmak için: {result['start_command']}")
    return 0 if result["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
