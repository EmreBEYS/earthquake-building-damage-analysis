from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


def test_map_page_handles_an_empty_unmapped_official_table() -> None:
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=60)
    app.sidebar.radio[0].set_value("Harita · Katmanlar").run(timeout=60)

    assert not app.exception



def test_change_page_handles_missing_snapshots() -> None:
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=60)
    app.sidebar.radio[0].set_value("2022–2023 Değişim Analizi").run(timeout=60)
    assert not app.exception
    assert any("veri dosyası henüz yok" in item.value for item in app.caption)


def test_reconstruction_page_renders_with_or_without_outputs() -> None:
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=60)
    app.sidebar.radio[0].set_value("2023–2026 Yeniden Yapılanma").run(timeout=120)
    assert not app.exception
    assert any("Yeniden Yapılanma" in item.value for item in app.header)


def test_spatial_analysis_page_renders_all_display_modes() -> None:
    page = "Mekânsal Analiz ve Mahalle Karşılaştırması"
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=60)
    app.sidebar.radio[0].set_value(page).run(timeout=120)
    assert not app.exception
    assert any("Mekânsal Analiz" in item.value for item in app.header)
    if (ROOT / "data/dashboard/sprint_00-20/neighborhood_spatial_analysis.geojson").exists():
        mode = next(radio for radio in app.sidebar.radio if radio.label == "Gösterim")
        for choice in ("Gi* sıcak nokta", "LISA küme"):
            mode.set_value(choice).run(timeout=120)
            assert not app.exception
