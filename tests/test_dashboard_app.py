from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]

ALL_PAGES = [
    ("Ana Sayfa", None),
    ("Harita Analizi", "İnteraktif Harita"),
    ("Harita Analizi", "Gerçek Hasar Haritası"),
    ("Harita Analizi", "Harita · Katmanlar"),
    ("Model Tahmini", "Bina Tahmin Haritası"),
    ("Model Tahmini", "Model performansı"),
    ("Veri Setleri", "Veri kaynakları"),
    ("Veri Setleri", "V1 · Copernicus"),
    ("Veri Setleri", "V2 · Resmî kayıtlar"),
    ("İstatistikler", "Mekânsal Analiz ve Mahalle Karşılaştırması"),
    ("İstatistikler", "V3 · Mekânsal"),
    ("Karşılaştırma", "2022–2023 Değişim Analizi"),
    ("Karşılaştırma", "2023–2026 Yeniden Yapılanma"),
    ("Karşılaştırma", "Uydu · Zaman Serisi"),
    ("Rapor & İndirme", None),
    ("Yöntem", None),
]


def open_page(menu: str, page: str | None = None) -> AppTest:
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=120)
    app.sidebar.radio(key="menu").set_value(menu).run(timeout=120)
    if page is not None:
        app.radio(key=f"page_{menu}").set_value(page).run(timeout=120)
    return app


@pytest.mark.parametrize(("menu", "page"), ALL_PAGES)
def test_every_page_renders_without_exceptions(menu, page) -> None:
    app = open_page(menu, page)
    assert not app.exception, [item.value for item in app.exception]


def test_home_page_kpis_come_from_project_outputs() -> None:
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=120)
    assert not app.exception
    html = "".join(item.body for item in app.markdown)
    assert "46.563" in html  # official record total, formatted with a Turkish separator
    assert "kpi-card" in html and "source-badge" in html


@pytest.mark.parametrize("period", ["2022", "2023", "2026"])
def test_period_selector_switches_home_map(period) -> None:
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=120)
    app.radio(key="period").set_value(period).run(timeout=120)
    assert not app.exception


def test_change_page_handles_missing_snapshots() -> None:
    app = open_page("Karşılaştırma", "2022–2023 Değişim Analizi")
    assert not app.exception
    if not (ROOT / "data/external/building_change/buildings_2022.geojson").exists():
        assert any("veri dosyası henüz yok" in item.value for item in app.caption)


def test_reconstruction_page_renders_with_or_without_outputs() -> None:
    app = open_page("Karşılaştırma", "2023–2026 Yeniden Yapılanma")
    assert not app.exception
    assert any("Yeniden Yapılanma" in item.value for item in app.header)


def test_spatial_analysis_page_renders_all_display_modes() -> None:
    app = open_page("İstatistikler", "Mekânsal Analiz ve Mahalle Karşılaştırması")
    assert not app.exception
    assert any("Mekânsal Analiz" in item.value for item in app.header)
    if (ROOT / "data/dashboard/sprint_00-20/neighborhood_spatial_analysis.geojson").exists():
        mode = next(radio for radio in app.sidebar.radio if radio.label == "Gösterim")
        for choice in ("Gi* sıcak nokta", "LISA küme"):
            mode.set_value(choice).run(timeout=120)
            assert not app.exception


@pytest.mark.parametrize("period", ["2022", "2023", "2026"])
def test_interactive_map_periods_focus_and_comparison(period) -> None:
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=120)
    app.radio(key="period").set_value(period).run(timeout=120)
    app.sidebar.radio(key="menu").set_value("Harita Analizi").run(timeout=120)
    app.radio(key="page_Harita Analizi").set_value("İnteraktif Harita").run(timeout=120)
    assert not app.exception
    app.sidebar.selectbox(key="imap_focus").set_value("Dabakhane Mahallesi").run(timeout=180)
    assert not app.exception
    for layer in ("osm_2022", "osm_2023", "osm_2026", "spectral_2022_2023"):
        boxes = [box for box in app.sidebar.checkbox if box.key == f"imap_{period}_{layer}"]
        for box in boxes:
            box.check().run(timeout=180)
            assert not app.exception
    app.radio(key="imap_mode").set_value("Yan yana karşılaştırma").run(timeout=180)
    assert not app.exception
    app.radio(key="imap_comparison").set_value("Gerçek ↔ Tahmin (2023)").run(timeout=180)
    assert not app.exception


def test_building_panel_shows_selected_polygon_details() -> None:
    app = AppTest.from_file(ROOT / "dashboard.py").run(timeout=120)
    app.sidebar.radio(key="menu").set_value("Harita Analizi").run(timeout=120)
    app.radio(key="page_Harita Analizi").set_value("İnteraktif Harita").run(timeout=120)
    picker = app.selectbox(key="imap_picker")
    picker.set_value(picker.options[-1]).run(timeout=120)
    assert not app.exception
    html = "".join(item.body for item in app.markdown)
    assert picker.value in html and "2023→2026 durumu" in html


@pytest.mark.parametrize("kind", ["Mahalle analiz raporu", "Yapı alanı (bina) raporu",
                                  "Model performans raporu", "Veri kalitesi raporu"])
def test_report_page_builds_every_report_type(kind) -> None:
    app = open_page("Rapor & İndirme")
    app.radio(key="report_kind").set_value(kind).run(timeout=240)
    assert not app.exception, [item.value for item in app.exception]
    assert any(kind.split(" (")[0].split(" raporu")[0] in item.value for item in app.subheader)
