from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_map_page_handles_an_empty_unmapped_official_table() -> None:
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=60)
    app.sidebar.radio[0].set_value("Harita · Katmanlar").run(timeout=60)

    assert not app.exception
