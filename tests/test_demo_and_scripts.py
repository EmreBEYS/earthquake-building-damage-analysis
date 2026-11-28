"""Sprint 00-24 — functional smoke tests: demo check and every script compiles."""

import importlib.util
import py_compile
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = sorted((ROOT / "scripts").glob("*.py"))


def _load_demo_check():
    spec = importlib.util.spec_from_file_location("demo_check", ROOT / "scripts/demo_check.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["demo_check"] = module
    spec.loader.exec_module(module)
    return module


def test_demo_check_passes_on_the_repository():
    result = _load_demo_check().run_checks(port=65432)
    failed = [item for item in result["checks"] if item["required"] and not item["ok"]]
    assert result["ready"], failed
    assert result["start_command"].startswith("uv run python -m streamlit run dashboard.py")


def test_demo_check_reports_missing_required_files(tmp_path):
    demo = _load_demo_check()
    (tmp_path / "dashboard.py").write_text("print('ok')\n", encoding="utf-8")
    result = demo.run_checks(root=tmp_path, port=65432)
    assert not result["ready"]
    missing = {item["check"] for item in result["checks"] if not item["ok"] and item["required"]}
    assert "dosya: data/dashboard/sprint_00-20/neighborhood_spatial_analysis.geojson" in missing
    optional = [item for item in result["checks"] if not item["required"]]
    assert optional and all(item["check"].startswith(("yerel veri", "port")) for item in optional)


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda path: path.name)
def test_every_script_compiles(script):
    py_compile.compile(str(script), doraise=True)
