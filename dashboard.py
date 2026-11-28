"""Malatya Deprem Projesi — Streamlit dashboard (Sprint 00-21 tasarımı).

Koyu tema, sol menü, KPI kartları, dönem seçimi ve her sayfada veri kaynağı göstergeleri.
Sayfa içerikleri önceki sprintlerin bölümleridir; ana sayfa yalnız depodaki çıktılardan
hesaplanan değerleri gösterir.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from earthquake_damage.dashboard_data import (
    DashboardDataError,
    load_dashboard_reports,
)
from earthquake_damage.geospatial_layers import (
    GeospatialLayerError,
    filter_feature_collection,
    load_map_layers,
)
from earthquake_damage.sprint_00_15 import (
    OFFICIAL_SEVERE_RATIO_BANDS,
    RealDamageMapError,
    load_real_damage_map,
    official_severe_ratio_band,
)
from earthquake_damage.sprint_00_17 import PredictionMapError, load_prediction_map
from earthquake_damage.ui.overview import (
    PERIOD_SOURCES,
    PERIODS,
    district_class_summary,
    official_class_summary,
    source_status,
)
from earthquake_damage.ui.theme import (
    CSS,
    format_int,
    format_pct,
    header_html,
    kpi_card_html,
    kpi_grid_html,
    source_badges_html,
)

ROOT = Path(__file__).resolve().parent
MAP_CENTER = {"lat": 38.345, "lon": 38.30}
SATELLITE_TILES = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
SATELLITE_ATTRIBUTION = "Esri, Maxar, Earthstar Geographics, and the GIS User Community"
CHART_LAYOUT = {
    "paper_bgcolor": "rgba(0,0,0,0)",
    "plot_bgcolor": "rgba(0,0,0,0)",
    "font": {"color": "#E6EDF6"},
    "margin": {"l": 10, "r": 10, "t": 30, "b": 10},
}

st.set_page_config(
    page_title="Malatya Deprem Projesi",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown(CSS, unsafe_allow_html=True)


def show_sources(*keys: str) -> None:
    """Data-source indicator row: which files this page reads and whether they exist."""
    st.markdown(source_badges_html([source_status(ROOT, key) for key in keys]),
                unsafe_allow_html=True)


def satellite_map_layout(height: int, zoom: float = 11.2) -> dict:
    return {
        "map": {
            "style": "white-bg",
            "center": MAP_CENTER,
            "zoom": zoom,
            "layers": [{"sourcetype": "raster", "source": [SATELLITE_TILES], "below": "traces"}],
        },
        "height": height,
        "margin": {"l": 0, "r": 0, "t": 0, "b": 0},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "legend": {"orientation": "h", "y": 1.02, "font": {"color": "#E6EDF6"}},
    }


@st.cache_data(show_spinner=False)
def read_csv(relative: str) -> pd.DataFrame | None:
    path = ROOT / relative
    return pd.read_csv(path) if path.exists() else None


@st.cache_data(show_spinner=False)
def read_json(relative: str) -> dict | None:
    path = ROOT / relative
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


# ---------------------------------------------------------------------------
# Header: title, period selector, project info
# ---------------------------------------------------------------------------

title_col, period_col, about_col = st.columns([4, 4.3, 1.5], vertical_alignment="center")
with title_col:
    st.markdown(
        header_html(
            "Malatya Deprem Projesi",
            "Açık Coğrafi Veriler ile Bina Hasar Seviyelerinin Makine Öğrenmesiyle Tahmini",
        ),
        unsafe_allow_html=True,
    )
with period_col:
    period = st.radio(
        "Dönem seçin",
        list(PERIODS),
        index=1,
        format_func=PERIODS.get,
        horizontal=True,
        key="period",
    )
with about_col:
    with st.popover("Hakkında", icon=":material/info:", width="stretch"):
        st.markdown(
            "6 Şubat 2023 depremlerinden sonra Malatya'nın Battalgazi ve Yeşilyurt ilçelerinde "
            "bina hasarını ve kent dönüşümünü açık verilerle inceleyen, tekrar üretilebilir bir "
            "araştırma projesi.\n\n"
            "- Resmî hasar kayıtları, Copernicus EMSR648, OpenStreetMap ve Sentinel-2\n"
            "- Keşif amaçlı makine öğrenmesi modelleri ve mekânsal istatistik\n\n"
            "**Bu arayüz araştırma amaçlıdır.** Sonuçlar bina güvenliği, tahliye, güçlendirme "
            "veya resmî hasar kararı için kullanılamaz."
        )

try:
    reports = load_dashboard_reports()
except DashboardDataError as error:
    st.error(str(error))
    st.info(
        "README'deki veri edinme adımlarını uygulayın veya eksik raporları "
        "reports/sprint_00-10 altında yeniden üretin."
    )
    st.stop()


# ---------------------------------------------------------------------------
# Home page (Sprint 00-21)
# ---------------------------------------------------------------------------


def section_home() -> None:
    """Ana Sayfa"""
    statistics = read_csv("data/dashboard/sprint_00-15/official_neighborhood_statistics.csv")
    districts = read_csv("data/dashboard/sprint_00-21/neighborhood_districts.csv")
    if statistics is None:
        st.warning("Resmî hasar istatistikleri bulunamadı (Sprint 00-15 çıktısı).")
        return
    show_sources(*PERIOD_SOURCES[period])

    classes = official_class_summary(statistics)
    total = sum(row["count"] for row in classes)
    icons = {"no_damage": "✓", "slight_damage": "◔", "moderate_damage": "◑",
             "heavy_damage": "◕", "urgent_demolition": "⚠", "destroyed": "✕"}
    cards = [kpi_card_html("Resmî kayıt", format_int(total),
                           "87 mahalle", "#93A3BD", "▦")]
    cards += [
        kpi_card_html(row["label"], format_int(row["count"]), format_pct(row["share"]),
                      row["color"], icons[row["key"]])
        for row in classes
    ]
    st.markdown(kpi_grid_html(cards), unsafe_allow_html=True)

    map_col, chart_col = st.columns([2, 1], gap="medium")
    with map_col, st.container(border=True):
        period_maps = {
            "2022": ("spectral_change_2022_2023_pct",
                     "2022→2023 spektral değişim alanı payı (%) · Sentinel-2", "Purples"),
            "2023": ("official_severe_ratio", "Resmî ağır hasar oranı · Bakanlık kayıtları",
                     "YlOrRd"),
            "2026": ("net_building_loss_pct",
                     "2023→2026 net OSM bina kaybı (%) · OSM", "Reds"),
        }
        column, caption, scale = period_maps[period]
        st.markdown(f'<div class="panel-title">Malatya mahalle haritası — {PERIODS[period]}</div>',
                    unsafe_allow_html=True)
        layer = read_json("data/dashboard/sprint_00-20/neighborhood_spatial_analysis.geojson")
        if layer is None:
            st.info("Mahalle analiz katmanı yok: `python scripts/19_analyze_spatial_neighborhoods.py`")
        else:
            features = [dict(f, id=str(i)) for i, f in enumerate(layer["features"])]
            values = [f["properties"].get(column) for f in features]
            figure = go.Figure(go.Choroplethmap(
                geojson={"type": "FeatureCollection", "features": features},
                locations=[f["id"] for f in features], z=values, colorscale=scale,
                marker_opacity=0.72, marker_line_width=0.6, marker_line_color="#0B1220",
                colorbar={"title": "", "thickness": 12, "tickfont": {"color": "#E6EDF6"}},
                text=[f"<b>{f['properties']['mahalle']}</b><br>{caption}: {v}"
                      for f, v in zip(features, values, strict=True)],
                hovertemplate="%{text}<extra></extra>",
            ))
            figure.update_layout(**satellite_map_layout(height=470))
            st.plotly_chart(figure, width="stretch")
            st.caption(f"{caption}. Uydu altlığı: {SATELLITE_ATTRIBUTION}.")

    with chart_col:
        with st.container(border=True):
            st.markdown('<div class="panel-title">Hasar sınıfı dağılımı</div>',
                        unsafe_allow_html=True)
            donut = go.Figure(go.Pie(
                labels=[f"{row['label']} · {format_pct(row['share'])}" for row in classes],
                values=[row["count"] for row in classes],
                marker={"colors": [row["color"] for row in classes]},
                hole=0.55, sort=False, textinfo="none",
                hovertemplate="%{label}: %{value:,} kayıt (%{percent})<extra></extra>",
            ))
            donut.update_layout(**{**CHART_LAYOUT, "margin": {"l": 0, "r": 0, "t": 0, "b": 0}},
                                height=300, showlegend=True,
                                legend={"orientation": "h", "y": -0.05, "font": {"size": 11}})
            st.plotly_chart(donut, width="stretch")
        with st.container(border=True):
            st.markdown('<div class="panel-title">İlçelere göre hasar dağılımı</div>',
                        unsafe_allow_html=True)
            if districts is None:
                st.caption("Mahalle–ilçe tablosu yok: `python scripts/20_prepare_dashboard_overview.py`")
            else:
                rows = pd.DataFrame(district_class_summary(statistics, districts))
                bars = px.bar(rows, x="district", y="count", color="label", barmode="group",
                              color_discrete_map={r["label"]: r["color"] for r in classes},
                              labels={"district": "", "count": "Kayıt", "label": ""})
                bars.update_layout(**CHART_LAYOUT, height=260,
                                   legend={"orientation": "h", "y": -0.25, "font": {"size": 10}})
                st.plotly_chart(bars, width="stretch")

    change_col, model_col = st.columns([3, 2], gap="medium")
    with change_col, st.container(border=True):
        st.markdown('<div class="panel-title">Zaman içinde değişim</div>', unsafe_allow_html=True)
        recon = read_json("reports/sprint_00-19/reconstruction_validation.json")
        osm_2022 = source_status(ROOT, "osm_2022")
        c2022, c2023, c2026 = st.columns(3)
        c2022.metric("2022 · OSM binası", "kesit var" if osm_2022["available"] else "—",
                     help="2022-12-31 OSM bina kesiti (Sprint 00-18).")
        if not osm_2022["available"]:
            c2022.caption("2022 kesiti indiriliyor; Overpass yoğun.")
        if recon:
            post = recon["osm"]["post_event"]["selected"]
            current = recon["osm"]["current"]["selected"]
            counts = recon["osm"]["reconstruction_class_counts"]
            c2023.metric("2023 · OSM binası", format_int(post),
                         help="24 Şubat 2023 OSM kesiti, çalışma alanı içinde.")
            c2026.metric("2026 · OSM binası", format_int(current),
                         delta=format_int(current - post), delta_color="off",
                         help="27 Temmuz 2026 OSM kesiti.")
            st.caption(
                f"2023→2026: {format_int(counts['removed_candidate'])} kaldırılan, "
                f"{format_int(counts['new_candidate'])} yeni yapı adayı. OSM haritalama "
                "durumudur; yeni yapılar geç çizildiği için yeni yapılaşma eksik ölçülür."
            )
    with model_col, st.container(border=True):
        st.markdown('<div class="panel-title">Model performansı (mekânsal doğrulama)</div>',
                    unsafe_allow_html=True)
        metrics = read_csv("reports/sprint_00-16/model_comparison.csv")
        if metrics is None:
            st.caption("Model karşılaştırma raporu yok (Sprint 00-16).")
        else:
            spatial = metrics[metrics["split"] == "spatial_1km_groups"].set_index("model")
            forest, dummy = spatial.loc["random_forest"], spatial.loc["dummy"]
            m1, m2, m3 = st.columns(3)
            m1.metric("Doğruluk", f"{forest['accuracy']:.2f}".replace(".", ","))
            m2.metric("Macro-F1", f"{forest['macro_f1']:.2f}".replace(".", ","),
                      delta=f"{forest['macro_f1'] - dummy['macro_f1']:+.3f}".replace(".", ","),
                      delta_color="off", help="Fark: sabit tahmin yapan dummy modele göre.")
            m3.metric("Ağırlıklı F1", f"{forest['weighted_f1']:.2f}".replace(".", ","))
            st.caption(
                "Random forest, 1 km mekânsal gruplu test. Yüksek doğruluk sınıf "
                "dengesizliğinden gelir (%90 hasarsız); macro-F1 sabit tahmin yapan dummy "
                "modelle aynı düzeydedir. Model operasyonel karar için yeterli değildir."
            )


def section_interactive_map() -> None:
    """İnteraktif Harita (Sprint 00-22)"""
    from earthquake_damage.interactive_map import render

    st.header("İnteraktif harita ve zaman paneli")
    show_sources("neighborhoods", "emsr648", "predictions", "reconstruction",
                 *(f"osm_{period}",))
    render(ROOT, period)


@st.cache_resource(show_spinner="Rapor verileri yükleniyor…")
def report_context() -> dict:
    from earthquake_damage.reporting import load_context

    return load_context(ROOT)


def section_reports() -> None:
    """Rapor & İndirme (Sprint 00-23)"""
    from earthquake_damage import reporting

    st.header("Rapor ve indirme")
    show_sources("official", "emsr648", "predictions", "spatial", "reconstruction")
    try:
        context = report_context()
    except FileNotFoundError as error:
        st.warning(f"Rapor girdileri eksik: {error}")
        return
    kinds = {
        "Mahalle analiz raporu": "neighborhood",
        "Yapı alanı (bina) raporu": "building",
        "Model performans raporu": "model",
        "Veri kalitesi raporu": "quality",
    }
    kind = kinds[st.radio("Rapor türü", list(kinds), horizontal=True, key="report_kind")]
    if kind == "neighborhood":
        names = sorted(context["comparison"]["mahalle"])
        default = names.index("Dabakhane Mahallesi") if "Dabakhane Mahallesi" in names else 0
        subject = st.selectbox("Mahalle", names, index=default, key="report_hood")
        report = reporting.neighborhood_report(context, subject)
    elif kind == "building":
        hood = st.selectbox("Mahalle", sorted(context["details"]["mahalle"].unique()),
                            key="report_building_hood")
        ids = sorted(context["details"].loc[context["details"]["mahalle"] == hood, "feature_id"])
        subject = st.selectbox("EMSR648 poligonu", ids, key="report_building")
        report = reporting.building_report(context, subject)
    elif kind == "model":
        report = reporting.model_performance_report(context)
    else:
        report = reporting.data_quality_report(ROOT)

    with st.container(border=True):
        st.subheader(f"{report.title} — {report.subtitle}")
        st.caption(f"Üretim: {report.generated_at}")
        summary = reporting.summary_frame(report)
        st.dataframe(summary, width="stretch", hide_index=True)
        figure_names = list(report.figures)
        columns = st.columns(min(2, len(figure_names)) or 1)
        for column, name in zip(columns, figure_names, strict=False):
            column.pyplot(report.figures[name], clear_figure=False)
        for name, table in report.tables.items():
            with st.expander(f"{name} ({len(table)} satır)"):
                st.dataframe(table, width="stretch", hide_index=True)
        for note in report.notes:
            st.caption("• " + note)

    st.markdown('<div class="panel-title">İndir</div>', unsafe_allow_html=True)
    stem = report.slug()
    c1, c2, c3, c4 = st.columns(4)
    c1.download_button("CSV", reporting.to_csv(report), file_name=f"{stem}.csv",
                       mime=reporting.MIME_TYPES["csv"], icon=":material/table:",
                       width="stretch", key=f"dl_csv_{stem}")
    c2.download_button("Excel", reporting.to_excel(report), file_name=f"{stem}.xlsx",
                       mime=reporting.MIME_TYPES["xlsx"], icon=":material/grid_on:",
                       width="stretch", key=f"dl_xlsx_{stem}")
    c3.download_button("PDF", reporting.to_pdf(report), file_name=f"{stem}.pdf",
                       mime=reporting.MIME_TYPES["pdf"], icon=":material/picture_as_pdf:",
                       width="stretch", key=f"dl_pdf_{stem}")
    figure_choice = c4.selectbox("PNG grafiği", figure_names, key=f"png_choice_{kind}",
                                 label_visibility="collapsed")
    c4.download_button("PNG", reporting.to_png(report.figures[figure_choice]),
                       file_name=f"{stem}_{figure_choice}.png", mime=reporting.MIME_TYPES["png"],
                       icon=":material/image:", width="stretch", key=f"dl_png_{stem}")
    import matplotlib.pyplot as plt

    plt.close("all")


def section_sources() -> None:
    """Veri kaynakları"""
    st.header("Veri kaynakları")
    st.caption("Panelin okuduğu her veri seti, rolü, kullanım koşulları ve dosya durumu.")
    from earthquake_damage.ui.overview import DATA_SOURCES

    rows = []
    for key in DATA_SOURCES:
        entry = source_status(ROOT, key)
        state = ("Eksik" if not entry["available"]
                 else "Yerel (Git dışı)" if entry["local_only"] else "Depoda")
        rows.append({"Veri seti": entry["name"], "Rol": entry["role"], "Sprint": entry["sprint"],
                     "Durum": state, "Boyut (MB)": entry.get("size_mb"),
                     "Güncelleme": entry.get("modified"), "Koşullar": entry["terms"],
                     "Dosya": entry["path"]})
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.markdown(source_badges_html([source_status(ROOT, key) for key in DATA_SOURCES]),
                unsafe_allow_html=True)
    st.caption("Yeşil: depoda · Sarı: yalnız yerel, Git dışında (lisans/boyut) · Kırmızı: eksik.")


def section_model_performance() -> None:
    """Model performansı"""
    st.header("Model performansı")
    show_sources("emsr648", "predictions")
    metrics = read_csv("reports/sprint_00-16/model_comparison.csv")
    if metrics is None:
        st.info("Sprint 00-16 model karşılaştırma raporu bulunamadı.")
        return
    labels = {"stratified_random": "Rastgele tabakalı", "spatial_1km_groups": "Mekânsal (1 km)"}
    table = metrics.assign(split=metrics["split"].map(labels))
    figure = px.bar(table, x="model", y="macro_f1", color="split", barmode="group",
                    error_y=table["macro_f1_ci_upper"] - table["macro_f1"],
                    error_y_minus=table["macro_f1"] - table["macro_f1_ci_lower"],
                    labels={"model": "", "macro_f1": "Macro-F1 (%95 GA)", "split": "Bölme"})
    figure.update_layout(**CHART_LAYOUT, height=380)
    st.plotly_chart(figure, width="stretch")
    st.dataframe(table.round(4), width="stretch", hide_index=True)
    report = read_json("reports/sprint_00-16/model_evaluation_report.json")
    if report:
        st.warning(report["conclusion"])


# ---------------------------------------------------------------------------
# Sections from earlier sprints
# ---------------------------------------------------------------------------


def section_change_2022_2023() -> None:
    """2022–2023 Değişim Analizi"""
    st.header("2022–2023 Değişim Analizi")
    show_sources("osm_2022", "change_2022_2023", "emsr648")
    st.info(
        "Tarihli OSM kesitleri haritalama durumunu; Sentinel-2 katmanı ise bulut maskeli "
        "NDVI, NDBI ve NBR farklarından türetilen spektral değişim adaylarını gösterir. "
        "İki katman da tek başına inşaat, yıkım veya bina hasarı kanıtı değildir."
    )
    root = Path(__file__).resolve().parent
    output = root / "data/dashboard/sprint_00-18"
    report_path = root / "reports/sprint_00-18/validation_report.json"
    satellite_report_path = root / "reports/sprint_00-18/satellite_change_validation.json"
    if report_path.exists():
        audit = json.loads(report_path.read_text(encoding="utf-8"))
        if audit.get("status") == "blocked":
            tiles = root / "data/external/building_change/tiles"
            downloaded = len(list(tiles.glob("*.json"))) if tiles.exists() else 0
            st.warning(
                "OSM bina değişimi (2022→2023) henüz hazır değil: tarihli OSM kesitleri "
                f"Overpass'tan karo karo indiriliyor ({downloaded}/18 karo). Sunucu yoğun "
                "olduğunda istekler geçici 502/504 hatası alır ve yeniden denenir. Aşağıdaki "
                "Sentinel-2 spektral değişim katmanı bundan etkilenmez."
            )
            with st.expander("Son teknik hata"):
                st.code(audit.get("reason", "Veri eksik"), language=None)
    if not (output / "building_change_2022_2023.geojson").exists():
        st.info("2022 ve 2023 bina kesitlerini edinmek için: "
                "`python scripts/16_analyze_building_change.py --acquire`")
    layer_paths = {
        "2022 · Deprem öncesi": output / "buildings_2022.geojson",
        "2023 · Deprem sonrası": output / "buildings_2023.geojson",
        "OSM haritalama değişimi": output / "building_change_2022_2023.geojson",
        "Uydu spektral değişim adayı": output / "pre_post_change_map.geojson",
        "Gerçek hasar · Copernicus": root / "data/dashboard/sprint_00-12/"
        "copernicus_damage_polygons.geojson",
        "Tahmin edilen hasar": root / "data/dashboard/sprint_00-17/predicted_damage.geojson",
    }
    colors = ["#2878b5", "#37a055", "#c97513", "#f28e2b", "#c74343", "#8b52bc"]
    figure = go.Figure()
    for (label, path), color in zip(layer_paths.items(), colors):
        visible = st.sidebar.checkbox(
            label,
            value=(label == "Uydu spektral değişim adayı" and path.exists()),
            disabled=not path.exists(),
            key="change_" + label,
        )
        if not path.exists():
            st.caption(label + ": veri dosyası henüz yok.")
        if not visible or not path.exists():
            continue
        collection = json.loads(path.read_text(encoding="utf-8"))
        features = collection["features"]
        groups = sorted({f["properties"].get("status", label) for f in features})
        for group in groups:
            subset = [dict(f, id=str(i)) for i, f in enumerate(features)
                      if f["properties"].get("status", label) == group]
            figure.add_trace(go.Choroplethmap(
                geojson={"type": "FeatureCollection", "features": subset},
                locations=[f["id"] for f in subset], z=[1] * len(subset),
                colorscale=[[0, color], [1, color]], showscale=False,
                marker_opacity=0.55, marker_line_width=1,
                name=label + " · " + group, showlegend=True,
                text=[json.dumps(f["properties"], ensure_ascii=False) for f in subset],
                hovertemplate="%{text}<extra></extra>",
            ))
    figure.update_layout(map_style="open-street-map", map_zoom=11,
                         map_center={"lat": 38.34, "lon": 38.29}, height=650,
                         margin={"l": 0, "r": 0, "t": 0, "b": 0})
    st.plotly_chart(figure, width="stretch")
    st.caption(
        "Sentinel-2 adayları 10 m çözünürlüktedir ve bina ölçeğinde karar değildir. "
        "© OpenStreetMap contributors · Contains modified Copernicus Sentinel data 2022–2023 "
        "· Copernicus EMS © European Union 2023"
    )
    if satellite_report_path.exists():
        satellite_report = json.loads(satellite_report_path.read_text(encoding="utf-8"))
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Ortak geçerli AOI", f"{satellite_report['cloud_mask']['joint_valid_aoi_percent']:.1f}%")
        col2.metric("Aday bileşen", f"{satellite_report['candidate_components']:,}")
        col3.metric("Aday alan", f"{satellite_report['candidate_area_m2'] / 1_000_000:.2f} km²")
        col4.metric(
            "EMSR648 kesişen poligon",
            f"{satellite_report['emsr648_polygons_with_candidate_pixels']:,}",
        )
        st.dataframe(
            pd.DataFrame(satellite_report["emsr648_by_damage_grade"]),
            width="stretch",
            hide_index=True,
        )
        st.warning(
            "Eşikler yerel saha verisiyle kalibre edilmemiş tarama kurallarıdır. "
            "EMSR648 kesişimi mekânsal birlikteliktir; doğruluk veya nedensellik ölçüsü değildir."
        )
    summary_path = output / "neighborhood_change_summary.csv"
    if summary_path.exists():
        st.dataframe(pd.read_csv(summary_path), width="stretch")
        st.download_button("Mahalle özetini indir", summary_path.read_bytes(),
                           file_name=summary_path.name, mime="text/csv")
    comparison_path = output / "satellite_emsr648_comparison.csv"
    map_path = output / "pre_post_change_map.geojson"
    if comparison_path.exists():
        st.download_button(
            "Uydu–EMSR648 ölçümlerini indir",
            comparison_path.read_bytes(),
            file_name=comparison_path.name,
            mime="text/csv",
        )
    if map_path.exists():
        st.download_button(
            "pre_post_change_map indir",
            map_path.read_bytes(),
            file_name=map_path.name,
            mime="application/geo+json",
        )



def section_reconstruction() -> None:
    """2023–2026 Yeniden Yapılanma"""
    from earthquake_damage.reconstruction_change_analysis import CLASS_LABELS_TR

    st.header("2023–2026 Yeniden Yapılanma Analizi")
    show_sources("osm_2023", "osm_2026", "reconstruction", "emsr648")
    st.info(
        "24 Şubat 2023 ile 2026 arasındaki fiziksel kent dönüşümünü iki bağımsız kanıtla "
        "gösterir: tarihli OSM bina ayak izleri ve ofset düzeltilmiş Sentinel-2 L2A spektral "
        "farkı. Sınıflar **değişim** sınıflarıdır; hasar sınıfı değildir ve hasar "
        "bilgisiyle birleştirilmez."
    )
    root = Path(__file__).resolve().parent
    output = root / "data/dashboard/sprint_00-19"
    report_path = root / "reports/sprint_00-19/reconstruction_validation.json"
    map_path = output / "reconstruction_change_map.geojson"
    indicators_path = output / "neighborhood_reconstruction_indicators.csv"
    context_path = output / "reconstruction_vs_emsr648_context.csv"
    if not map_path.exists():
        st.caption("reconstruction_change_map: veri dosyası henüz yok.")
        st.info("Üretmek için: `python scripts/18_analyze_reconstruction_change.py all`")
    else:
        class_colors = {
            "removed_candidate": "#c74343",
            "new_candidate": "#2e9d5b",
            "modified_candidate": "#e0a526",
            "uncertain": "#8c8c8c",
            "spectral_only_change": "#7a5bbf",
        }
        with st.sidebar:
            st.subheader("Yeniden yapılanma katmanları")
            selected_classes = [
                key
                for key, label in CLASS_LABELS_TR.items()
                if key in class_colors
                and st.checkbox(
                    label,
                    value=key in {"removed_candidate", "new_candidate"},
                    key="recon_" + key,
                )
            ]
            supported_only = st.checkbox("Yalnız OSM + uydu destekli", value=False)
        collection = json.loads(map_path.read_text(encoding="utf-8"))
        figure = go.Figure()
        for key in selected_classes:
            subset = [
                dict(feature, id=str(index))
                for index, feature in enumerate(collection["features"])
                if feature["properties"]["reconstruction_class"] == key
                and (
                    not supported_only
                    or feature["properties"]["evidence"] in {"osm_and_spectral", "spectral_only"}
                )
            ]
            if not subset:
                continue
            figure.add_trace(
                go.Choroplethmap(
                    geojson={"type": "FeatureCollection", "features": subset},
                    locations=[feature["id"] for feature in subset],
                    z=[1] * len(subset),
                    colorscale=[[0, class_colors[key]], [1, class_colors[key]]],
                    showscale=False,
                    marker_opacity=0.7,
                    marker_line_width=0.5,
                    name=f"{CLASS_LABELS_TR[key]} ({len(subset):,})",
                    showlegend=True,
                    text=[
                        "<br>".join(
                            f"{name}: {feature['properties'].get(name)}"
                            for name in (
                                "unit_id", "neighborhood", "evidence",
                                "footprint_area_m2", "spectral_change_fraction",
                                "direction_hint",
                            )
                        )
                        for feature in subset
                    ],
                    hovertemplate="%{text}<extra></extra>",
                )
            )
        figure.update_layout(
            map_style="open-street-map",
            map_zoom=11.5,
            map_center={"lat": 38.345, "lon": 38.31},
            height=650,
            margin={"l": 0, "r": 0, "t": 0, "b": 0},
            legend={"orientation": "h", "y": 1.02},
        )
        st.plotly_chart(figure, width="stretch")
        st.caption(
            "© OpenStreetMap contributors (ODbL) · Contains modified Copernicus Sentinel "
            "data 2023–2026 · Sürekli (persistent) ayak izleri haritada çizilmez, sayılır."
        )
        st.download_button(
            "reconstruction_change_map indir",
            map_path.read_bytes(),
            file_name=map_path.name,
            mime="application/geo+json",
        )
    if report_path.exists():
        recon_report = json.loads(report_path.read_text(encoding="utf-8"))
        counts = recon_report["osm"]["reconstruction_class_counts"]
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Kaldırılmış yapı adayı", f"{counts.get('removed_candidate', 0):,}")
        col2.metric("Yeni görünen yapı adayı", f"{counts.get('new_candidate', 0):,}")
        col3.metric(
            "Net ayak izi değişimi",
            f"{recon_report['osm']['net_footprint_count_change']:+,}",
        )
        col4.metric(
            "Ortak geçerli uydu alanı",
            f"{recon_report['sentinel2']['joint_valid_aoi_percent']:.1f}%",
        )
        st.caption(
            f"OSM: {recon_report['period']['osm_post_event'][:10]} → "
            f"{recon_report['period']['osm_current'][:10]} · Sentinel-2: "
            f"{recon_report['period']['sentinel2_post'][:10]} → "
            f"{recon_report['period']['sentinel2_current'][:10]}"
        )
    if indicators_path.exists():
        indicators = pd.read_csv(indicators_path)
        st.subheader("Mahalle bazlı yapılaşma göstergeleri")
        ranked = indicators[indicators["neighborhood"] != "unknown"].copy()
        melted = ranked.nlargest(15, "renewal_turnover_pct").melt(
            id_vars="neighborhood",
            value_vars=["removed_candidates", "new_candidates"],
            var_name="gösterge",
            value_name="ayak izi",
        )
        melted["gösterge"] = melted["gösterge"].map(
            {"removed_candidates": "Kaldırılmış aday", "new_candidates": "Yeni aday"}
        )
        st.plotly_chart(
            px.bar(
                melted,
                x="ayak izi",
                y="neighborhood",
                color="gösterge",
                barmode="group",
                orientation="h",
                color_discrete_map={"Kaldırılmış aday": "#c74343", "Yeni aday": "#2e9d5b"},
                title="Yenilenme devri en yüksek 15 mahalle",
            ).update_layout(height=520, yaxis_title=None),
            width="stretch",
        )
        st.dataframe(indicators, width="stretch", hide_index=True)
        st.download_button(
            "Mahalle göstergelerini indir",
            indicators_path.read_bytes(),
            file_name=indicators_path.name,
            mime="text/csv",
        )
    if context_path.exists():
        with st.expander("Ayrı bağlam: EMSR648 hasar poligonlarıyla mekânsal birliktelik"):
            st.warning(
                "Bu tablo değişim birimlerinin Copernicus hasar poligonlarıyla kesişimini sayar. "
                "Bir yapının kaldırılması hasar sınıfı anlamına gelmez; doğruluk ölçüsü değildir."
            )
            st.dataframe(pd.read_csv(context_path), width="stretch", hide_index=True)



def section_spatial() -> None:
    """Mekânsal Analiz ve Mahalle Karşılaştırması"""
    from earthquake_damage.spatial_analysis import HOTSPOT_LABELS_TR, LISA_LABELS_TR

    st.header("Mekânsal Analiz ve Mahalle Karşılaştırması")
    show_sources("official", "emsr648", "predictions", "osm_2023", "spatial")
    st.info(
        "Resmî hasar kayıtları, EMSR648, bina yoğunluğu ve 2023–2026 değişimi mahalle "
        "düzeyinde yan yana konur. Sıcak noktalar Getis-Ord Gi*, kümeler yerel Moran (LISA) "
        "ile bulunur. Kaynaklar birleştirilmez; yalnız karşılaştırılır."
    )
    root = Path(__file__).resolve().parent
    output = root / "data/dashboard/sprint_00-20"
    layer_path = output / "neighborhood_spatial_analysis.geojson"
    table_path = output / "neighborhood_comparison.csv"
    grid_path = output / "hotspot_grid.geojson"
    summary_path = output / "spatial_autocorrelation_summary.csv"
    report_path = root / "reports/sprint_00-20/spatial_analysis_validation.json"
    if not layer_path.exists():
        st.caption("Mekânsal analiz: veri dosyası henüz yok.")
        st.info("Üretmek için: `python scripts/19_analyze_spatial_neighborhoods.py`")
    else:
        config = json.loads((root / "configs/sprint_00_20.json").read_text(encoding="utf-8"))
        variables = config["hotspot_variables"]
        hotspot_colors = {
            "hot_99": "#b2182b", "hot_95": "#ef8a62", "hot_90": "#fddbc7",
            "not_significant": "#f2f2f2", "cold_90": "#d1e5f0", "cold_95": "#67a9cf",
            "cold_99": "#2166ac", "no_data": "#bdbdbd",
        }
        lisa_colors = {"HH": "#d7191c", "LL": "#2c7bb6", "HL": "#fdae61", "LH": "#abd9e9",
                       "not_significant": "#f2f2f2", "no_data": "#bdbdbd"}
        with st.sidebar:
            st.subheader("Mekânsal analiz")
            variable = st.selectbox(
                "Gösterge", list(variables), format_func=lambda key: variables[key]
            )
            mode = st.radio("Gösterim", ["Değer", "Gi* sıcak nokta", "LISA küme"])
            fdr_only = st.checkbox("Yalnız FDR ile anlamlı sıcak noktalar", value=False)
        collection = json.loads(layer_path.read_text(encoding="utf-8"))
        features = [dict(f, id=str(i)) for i, f in enumerate(collection["features"])]
        props = [f["properties"] for f in features]
        hover = [
            f"<b>{p['mahalle']}</b><br>{variables[variable]}: {p.get(variable)}"
            f"<br>Gi* z: {p.get(variable + '__gi_z')} · p: {p.get(variable + '__gi_p')}"
            f"<br>{HOTSPOT_LABELS_TR.get(p.get(variable + '__hotspot'), '')}"
            f" · {LISA_LABELS_TR.get(p.get(variable + '__lisa'), '')}"
            for p in props
        ]
        figure = go.Figure()
        if mode == "Değer":
            figure.add_trace(go.Choroplethmap(
                geojson={"type": "FeatureCollection", "features": features},
                locations=[f["id"] for f in features],
                z=[p.get(variable) for p in props],
                colorscale="YlOrRd", marker_opacity=0.75, marker_line_width=0.6,
                colorbar={"title": ""}, text=hover, hovertemplate="%{text}<extra></extra>",
            ))
        else:
            key = "__hotspot" if mode == "Gi* sıcak nokta" else "__lisa"
            colors = hotspot_colors if key == "__hotspot" else lisa_colors
            labels = HOTSPOT_LABELS_TR if key == "__hotspot" else LISA_LABELS_TR
            for category, color in colors.items():
                members = [
                    i for i, p in enumerate(props)
                    if p.get(variable + key) == category
                    and (not fdr_only or key != "__hotspot" or category.startswith(("not", "no"))
                         or p.get(variable + "__gi_fdr"))
                ]
                if not members:
                    continue
                figure.add_trace(go.Choroplethmap(
                    geojson={"type": "FeatureCollection",
                             "features": [features[i] for i in members]},
                    locations=[features[i]["id"] for i in members], z=[1] * len(members),
                    colorscale=[[0, color], [1, color]], showscale=False,
                    marker_opacity=0.8, marker_line_width=0.6,
                    name=f"{labels[category]} ({len(members)})", showlegend=True,
                    text=[hover[i] for i in members], hovertemplate="%{text}<extra></extra>",
                ))
        figure.update_layout(
            map_style="open-street-map", map_zoom=11.3,
            map_center={"lat": 38.345, "lon": 38.31}, height=620,
            margin={"l": 0, "r": 0, "t": 0, "b": 0}, legend={"orientation": "h", "y": 1.02},
        )
        st.plotly_chart(figure, width="stretch")
        st.caption(
            "Queen komşuluk, 999 permütasyon. %90/%95/%99 sınıfları tek tek testtir; 87 eşzamanlı "
            "test için doğrulayıcı ifade FDR bayrağına dayanmalıdır."
        )
    if summary_path.exists():
        st.subheader("Küresel Moran's I")
        summary = pd.read_csv(summary_path)
        st.dataframe(summary, width="stretch", hide_index=True)
    if report_path.exists():
        spatial_report = json.loads(report_path.read_text(encoding="utf-8"))
        st.subheader("Kaynaklar arası sıra korelasyonu (Spearman)")
        st.dataframe(pd.DataFrame(spatial_report["source_rank_correlations"]),
                     width="stretch", hide_index=True)
        st.caption(
            "Uyum ölçüsüdür, nedensellik değildir. 00-17 tahminleri modelin eğitildiği EMSR648 "
            "binalarını kapsadığından EMSR648 ile yüksek uyumu doğrulama sayılmaz."
        )
    if grid_path.exists():
        with st.expander("500 m grid sıcak noktaları"):
            grid_variable = st.radio(
                "Grid göstergesi", ["emsr_severe_share", "removed_share"], horizontal=True,
                format_func=lambda k: {"emsr_severe_share": "EMSR648 ağır hasar payı",
                                       "removed_share": "Kaldırılan yapı payı"}[k],
            )
            grid = json.loads(grid_path.read_text(encoding="utf-8"))
            cells = [dict(f, id=str(i)) for i, f in enumerate(grid["features"])]
            grid_figure = go.Figure()
            for category, color in hotspot_colors.items():
                members = [c for c in cells
                           if c["properties"].get(grid_variable + "__hotspot") == category]
                if not members or category == "no_data":
                    continue
                grid_figure.add_trace(go.Choroplethmap(
                    geojson={"type": "FeatureCollection", "features": members},
                    locations=[c["id"] for c in members], z=[1] * len(members),
                    colorscale=[[0, color], [1, color]], showscale=False,
                    marker_opacity=0.7, marker_line_width=0.3,
                    name=f"{HOTSPOT_LABELS_TR[category]} ({len(members)})",
                ))
            grid_figure.update_layout(
                map_style="open-street-map", map_zoom=11.3,
                map_center={"lat": 38.345, "lon": 38.31}, height=520,
                margin={"l": 0, "r": 0, "t": 0, "b": 0},
            )
            st.plotly_chart(grid_figure, width="stretch")
    if table_path.exists():
        st.subheader("Mahalle karşılaştırma tablosu")
        table = pd.read_csv(table_path)
        core = ["mahalle", "area_km2", "official_records", "official_severe",
                "official_severe_ratio", "official_severe_per_km2", "emsr_severe_share",
                "predicted_severe_share", "building_density_2023_km2",
                "removed_share_of_2023_pct", "new_footprint_density_per_km2",
                "spectral_change_2022_2023_pct", "rank_official_severe_ratio"]
        st.dataframe(table[core].sort_values("rank_official_severe_ratio"),
                     width="stretch", hide_index=True)
        st.download_button("Karşılaştırma tablosunu indir (CSV)", table_path.read_bytes(),
                           file_name=table_path.name, mime="text/csv")
        st.download_button("Mahalle analiz katmanını indir (GeoJSON)",
                           layer_path.read_bytes(), file_name=layer_path.name,
                           mime="application/geo+json")



def section_real_damage_map() -> None:
    """Gerçek Hasar Haritası"""
    st.header("Gerçek Hasar Haritası")
    show_sources("official", "emsr648", "neighborhoods")
    st.info(
        "Resmî PDF kayıtlarında doğrulanmış koordinat bulunmadığı için resmî hasar yalnız "
        "mahalle düzeyinde gösterilir. Copernicus EMSR648 poligonları bağımsız bir uydu-temelli "
        "gözlem katmanıdır; iki kaynak bina düzeyinde birleştirilmez."
    )
    try:
        real_map = load_real_damage_map()
    except RealDamageMapError as error:
        st.error(str(error))
        st.info("`python scripts/13_prepare_real_damage_map.py` komutuyla 00-15 çıktılarını üretin.")
        st.stop()

    official_classes = real_map.config["official_classes"]
    class_by_label = {item["label"]: item for item in official_classes}
    official_features = real_map.official_neighborhoods["features"]
    copernicus_features = real_map.copernicus_damage["features"]
    copernicus_grades = sorted(
        {feature["properties"]["damage_grade"] for feature in copernicus_features}
    )

    with st.sidebar:
        st.subheader("Gerçek hasar filtreleri")
        basemap = st.radio("Altlık", ["Uydu", "Sokak"], horizontal=True)
        show_official = st.checkbox("Resmî mahalle hasarı", value=True)
        selected_labels = st.multiselect(
            "Resmî hasar sınıfı",
            [item["label"] for item in official_classes],
            default=[item["label"] for item in official_classes],
        )
        min_official = st.slider("En az resmî kayıt", 0, 3_000, 0, 50)
        min_severe_percent = st.slider("En az ağır/acil/yıkık payı (%)", 0, 100, 0, 1)
        show_copernicus = st.checkbox("Copernicus poligonları", value=True)
        selected_copernicus = st.multiselect(
            "Copernicus hasar sınıfı", copernicus_grades, default=copernicus_grades
        )

    selected_keys = [class_by_label[label]["key"] for label in selected_labels]
    visible_official: list[dict] = []
    stats_rows: list[dict] = []
    for feature in official_features:
        properties = {**feature["properties"]}
        selected_count = sum(int(properties[key]) for key in selected_keys)
        severe_count = sum(
            int(properties[key]) for key in ("heavy_damage", "urgent_demolition", "destroyed")
        )
        severe_ratio = severe_count / properties["official_total"]
        if (
            properties["official_total"] < min_official
            or severe_ratio < min_severe_percent / 100
            or not selected_count
        ):
            continue
        severe_band = official_severe_ratio_band(severe_ratio)
        properties["display_count"] = selected_count
        properties["display_ratio"] = selected_count / properties["official_total"]
        properties["display_severe_count"] = severe_count
        properties["display_severe_ratio"] = severe_ratio
        properties["display_severe_band"] = severe_band["key"]
        visible_official.append({**feature, "properties": properties})
        stats_rows.append(properties)

    figure = go.Figure()
    if show_official:
        for band in OFFICIAL_SEVERE_RATIO_BANDS:
            features = [
                feature
                for feature in visible_official
                if feature["properties"]["display_severe_band"] == band["key"]
            ]
            if not features:
                continue
            collection = {
                **real_map.official_neighborhoods,
                "features": features,
            }
            properties = [feature["properties"] for feature in features]
            figure.add_trace(
                go.Choroplethmap(
                    geojson=collection,
                    locations=[value["neighborhood_id"] for value in properties],
                    z=[1] * len(properties),
                    featureidkey="properties.neighborhood_id",
                    colorscale=[[0, band["color"]], [1, band["color"]]],
                    showscale=False,
                    marker={"opacity": 0.52, "line": {"width": 1.2, "color": "#ffffff"}},
                    customdata=[
                        [
                            value["mahalle"],
                            value["official_total"],
                            value["display_count"],
                            value["display_ratio"],
                            value["display_severe_count"],
                            value["display_severe_ratio"],
                        ]
                        for value in properties
                    ],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>Resmî toplam: %{customdata[1]:,}"
                        "<br>Seçili sınıflar: %{customdata[2]:,} (%{customdata[3]:.1%})"
                        "<br>Ağır + acil + yıkık: %{customdata[4]:,} (%{customdata[5]:.1%})"
                        f"<br>Eşik: {band['label']}<extra></extra>"
                    ),
                    name=f"Resmî kritik pay · {band['label']}",
                )
            )

    copernicus_colors = {
        "Destroyed": "#7f0000",
        "Damaged": "#d7301f",
        "Possibly damaged": "#fc8d59",
        "No visible damage": "#2ca25f",
        "Unknown": "#756bb1",
    }
    visible_copernicus_count = 0
    if show_copernicus:
        for grade in selected_copernicus:
            collection = filter_feature_collection(
                real_map.copernicus_damage,
                property_name="damage_grade",
                accepted_values={grade},
            )
            features = collection["features"]
            visible_copernicus_count += len(features)
            if not features:
                continue
            color = copernicus_colors.get(grade, "#756bb1")
            figure.add_trace(
                go.Choroplethmap(
                    geojson=collection,
                    locations=[feature["properties"]["feature_id"] for feature in features],
                    z=[1] * len(features),
                    featureidkey="properties.feature_id",
                    colorscale=[[0, color], [1, color]],
                    showscale=False,
                    marker={"opacity": 0.78, "line": {"width": 0.25, "color": color}},
                    customdata=[
                        [feature["properties"]["feature_id"]] for feature in features
                    ],
                    hovertemplate=(
                        f"<b>Copernicus · {grade}</b>"
                        "<br>Poligon kimliği: %{customdata[0]}<extra></extra>"
                    ),
                    name=f"Copernicus · {grade}",
                )
            )

    map_layout: dict = {
        "center": {"lat": 38.343, "lon": 38.288},
        "zoom": 11,
        "style": "carto-positron",
    }
    if basemap == "Uydu":
        satellite = real_map.config["satellite_basemap"]
        map_layout = {
            "center": {"lat": 38.343, "lon": 38.288},
            "zoom": 11,
            "style": "white-bg",
            "layers": [
                {
                    "sourcetype": "raster",
                    "source": [satellite["tile_url"]],
                    "below": "traces",
                }
            ],
        }
    figure.update_layout(
        map=map_layout,
        height=760,
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01},
    )
    st.plotly_chart(figure, width="stretch")
    if basemap == "Uydu":
        st.caption(
            "Uydu altlığı: "
            f"{real_map.config['satellite_basemap']['attribution']}. "
            "Altlık yalnız görsel bağlamdır; resmî hasar kanıtı değildir."
        )

    selected_total = sum(row["display_count"] for row in stats_rows)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Görünen mahalle", len(stats_rows))
    col2.metric("Seçili resmî kayıt", f"{selected_total:,}")
    col3.metric("Resmî toplam", f"{real_map.validation['official_record_count']:,}")
    col4.metric("Görünen Copernicus poligonu", f"{visible_copernicus_count:,}")

    st.subheader("Mahalle istatistikleri")
    if stats_rows:
        stats_frame = pd.DataFrame(stats_rows)
        display_columns = [
            "mahalle",
            "official_total",
            *[item["key"] for item in official_classes],
            "severe_ratio",
        ]
        renamed = {
            "mahalle": "Mahalle",
            "official_total": "Toplam",
            "severe_ratio": "Ağır/acil/yıkık payı",
            **{item["key"]: item["label"] for item in official_classes},
        }
        st.dataframe(
            stats_frame[display_columns]
            .sort_values("severe_ratio", ascending=False)
            .rename(columns=renamed)
            .style.format({"Ağır/acil/yıkık payı": "{:.1%}"}),
            width="stretch",
            hide_index=True,
        )
    else:
        st.warning("Seçili sınıf ve kayıt eşiğiyle gösterilecek mahalle bulunamadı.")

    with st.expander("Kaynak ve eşleme kanıtı"):
        st.json(
            {
                "resmî_eşleme_düzeyi": real_map.manifest["official_mapping_level"],
                "resmî_koordinat_kanıtı": real_map.manifest[
                    "official_coordinate_evidence"
                ],
                "bina_düzeyi_kaynak_birleştirme": real_map.manifest["source_separation"][
                    "joined_at_building_level"
                ],
                "resmî_kayıt": real_map.validation["official_record_count"],
                "copernicus_poligonu": real_map.validation["copernicus_feature_count"],
            }
        )



def section_prediction_map() -> None:
    """Bina Tahmin Haritası"""
    st.header("Bina Bazlı Gerçek / Tahmin Haritası")
    show_sources("predictions", "emsr648")
    st.warning(
        "Tahminler araştırma amaçlıdır; resmî hasar veya bina güvenliği kararı değildir. "
        "Sprint 00-16 mekânsal değerlendirmesinde azınlık sınıfları zayıf kalmıştır."
    )
    try:
        prediction_map = load_prediction_map()
    except PredictionMapError as error:
        st.error(str(error))
        st.info(
            "Sprint 00-16'da doğrulanan random_forest.joblib dosyasını models/ altına "
            "yerleştirip `python scripts/15_generate_prediction_map.py` komutunu çalıştırın."
        )
        st.stop()

    features = prediction_map.predictions["features"]
    observed_classes = sorted({item["properties"]["observed_damage"] for item in features})
    predicted_classes = sorted({item["properties"]["predicted_damage"] for item in features})
    with st.sidebar:
        st.subheader("Tahmin katmanları")
        show_observed = st.checkbox("Gerçek Copernicus hasarı", value=True)
        show_predicted = st.checkbox("Model tahmini", value=True)
        show_low_confidence = st.checkbox("Düşük güvenli tahminler", value=True)
        selected_observed = st.multiselect(
            "Gerçek hasar sınıfı", observed_classes, default=observed_classes
        )
        selected_predicted = st.multiselect(
            "Tahmin sınıfı", predicted_classes, default=predicted_classes
        )

    colors = {
        "Destroyed": "#7f0000",
        "destroyed": "#7f0000",
        "Damaged": "#d7301f",
        "damaged": "#d7301f",
        "Possibly damaged": "#fc8d59",
        "possibly_damaged": "#fc8d59",
        "No visible damage": "#2ca25f",
        "no_visible_damage": "#2ca25f",
    }
    figure = go.Figure()

    def add_damage_traces(property_name: str, values: list[str], *, prefix: str, opacity: float) -> None:
        for value in values:
            layer_features = [
                item
                for item in features
                if item["properties"][property_name] == value
                and (show_low_confidence or not item["properties"]["low_confidence"])
            ]
            if not layer_features:
                continue
            color = colors.get(value, "#756bb1")
            figure.add_trace(
                go.Choroplethmap(
                    geojson={**prediction_map.predictions, "features": layer_features},
                    locations=[item["properties"]["feature_id"] for item in layer_features],
                    z=[1] * len(layer_features),
                    featureidkey="properties.feature_id",
                    colorscale=[[0, color], [1, color]],
                    showscale=False,
                    marker={"opacity": opacity, "line": {"width": 0.25, "color": color}},
                    customdata=[
                        [
                            item["properties"]["feature_id"],
                            item["properties"]["observed_damage"],
                            item["properties"]["predicted_damage"],
                            item["properties"]["confidence"],
                            item["properties"]["low_confidence"],
                        ]
                        for item in layer_features
                    ],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b>"
                        "<br>Gerçek: %{customdata[1]}"
                        "<br>Tahmin: %{customdata[2]}"
                        "<br>Güven: %{customdata[3]:.1%}"
                        "<br>Düşük güven: %{customdata[4]}<extra></extra>"
                    ),
                    name=f"{prefix} · {value}",
                )
            )

    if show_observed:
        add_damage_traces("observed_damage", selected_observed, prefix="Gerçek", opacity=0.42)
    if show_predicted:
        add_damage_traces("predicted_damage", selected_predicted, prefix="Tahmin", opacity=0.78)
    figure.update_layout(
        map={"style": "carto-positron", "center": {"lat": 38.343, "lon": 38.288}, "zoom": 11},
        height=760,
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01},
    )
    st.plotly_chart(figure, width="stretch")

    low_confidence_count = sum(item["properties"]["low_confidence"] for item in features)
    col1, col2, col3 = st.columns(3)
    col1.metric("Bina", f"{len(features):,}")
    col2.metric("Düşük güven", f"{low_confidence_count:,}")
    col3.metric("Güven eşiği", f"{prediction_map.config['low_confidence_threshold']:.0%}")
    with st.expander("Model ve veri sızıntısı kanıtı"):
        st.json(
            {
                "model": prediction_map.manifest["model"],
                "veri_sızıntısı": prediction_map.manifest["leakage_audit"],
                "sınırlamalar": prediction_map.manifest["limitations"],
            }
        )



def section_map_layers() -> None:
    """Harita · Katmanlar"""
    st.header("AOI05 coğrafi katmanları")
    show_sources("neighborhoods", "emsr648")
    st.info(
        "Resmî hasar kayıtları yalnızca mahalle toplamları olarak renklendirilir. "
        "Haritadaki Copernicus poligonları ayrı bir gözlem kaynağıdır; resmî kayıtların "
        "tekil binalara konumlandırıldığı veya iki kaynağın bina bazında eşleştiği anlamına gelmez."
    )
    try:
        layers = load_map_layers()
    except GeospatialLayerError as error:
        st.error(str(error))
        st.stop()

    neighborhood_features = layers.neighborhoods["features"]
    requested_boundary_features = layers.requested_boundaries["features"]
    damage_features = layers.damage_polygons["features"]
    damage_grades = sorted({feature["properties"]["damage_grade"] for feature in damage_features})
    person_groups = ["person_01", "person_02", "person_03"]

    with st.sidebar:
        st.subheader("Harita filtreleri")
        show_official = st.checkbox("Mahalle resmî hasar oranı", value=True)
        requested_boundaries_available = bool(requested_boundary_features)
        show_requested_boundaries = st.checkbox(
            "İncelenen mahalle sınırları",
            value=requested_boundaries_available,
            disabled=not requested_boundaries_available,
        )
        if not requested_boundaries_available:
            st.caption("Yeni mahalle sınırı katmanı henüz hazırlanmadı.")
        show_damage = st.checkbox("Copernicus hasar poligonları", value=True)
        selected_persons = st.multiselect("Resmî kayıt grubu", person_groups, default=person_groups)
        coverage_groups = sorted(
            {feature["properties"]["coverage_group"] for feature in neighborhood_features}
        )
        selected_coverage = st.multiselect(
            "AOI kapsam sınıfı", coverage_groups, default=coverage_groups
        )
        min_records = st.slider("En az resmî kayıt", 0, 3_000, 0, 50)
        selected_damage = st.multiselect(
            "Copernicus hasar sınıfı", damage_grades, default=damage_grades
        )

        display_features = []
        for feature in neighborhood_features:
            properties = {**feature["properties"]}
            properties["display_official_total"] = sum(
                properties[f"{person}_total"] for person in selected_persons
            )
            properties["display_severe_count"] = sum(
                properties[f"{person}_severe_count"] for person in selected_persons
            )
            properties["display_severe_ratio"] = (
                properties["display_severe_count"] / properties["display_official_total"]
                if properties["display_official_total"]
                else 0.0
            )
            display_features.append({**feature, "properties": properties})
        display_collection = {**layers.neighborhoods, "features": display_features}

        available_names = sorted(
            feature["properties"]["mahalle"]
            for feature in display_features
            if feature["properties"]["display_official_total"] >= min_records
            and feature["properties"]["coverage_group"] in selected_coverage
        )
        selected_names = st.multiselect("Mahalle", available_names, default=available_names)

    visible_neighborhoods = {
        feature["properties"]["neighborhood_id"]
        for feature in display_features
        if feature["properties"]["display_official_total"] >= min_records
        and feature["properties"]["coverage_group"] in selected_coverage
        and feature["properties"]["mahalle"] in selected_names
    }
    neighborhood_geojson = filter_feature_collection(
        display_collection,
        property_name="neighborhood_id",
        accepted_values=visible_neighborhoods,
    )
    filtered_neighborhoods = neighborhood_geojson["features"]

    figure = go.Figure()
    if show_official and filtered_neighborhoods:
        properties = [feature["properties"] for feature in filtered_neighborhoods]
        figure.add_trace(
            go.Choroplethmap(
                geojson=neighborhood_geojson,
                locations=[item["neighborhood_id"] for item in properties],
                z=[item["display_severe_ratio"] for item in properties],
                featureidkey="properties.neighborhood_id",
                colorscale="YlOrRd",
                zmin=0,
                zmax=0.6,
                marker={"opacity": 0.5, "line": {"width": 1.5, "color": "#202020"}},
                colorbar={"title": "Ağır/acil/yıkık<br>kayıt payı"},
                customdata=[
                    [
                        item["mahalle"],
                        item["display_official_total"],
                        item["display_severe_count"],
                        item["coverage_group"],
                        (
                            f"{item['aoi_coverage_ratio']:.1%}"
                            if item["aoi_coverage_ratio"] is not None
                            else "ad eşleştirmesi doğrulandı"
                        ),
                        item["match_method"],
                    ]
                    for item in properties
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>Resmî kayıt: %{customdata[1]:,}"
                    "<br>Ağır/acil/yıkık: %{customdata[2]:,}<br>Pay: %{z:.1%}"
                    "<br>AOI kapsamı: %{customdata[3]} (%{customdata[4]})"
                    "<br>Eşleştirme: %{customdata[5]}<extra></extra>"
                ),
                name="Mahalle toplamları",
            )
        )

    if show_requested_boundaries:
        requested_properties = [
            feature["properties"] for feature in requested_boundary_features
        ]
        figure.add_trace(
            go.Choroplethmap(
                geojson=layers.requested_boundaries,
                locations=[item["neighborhood_id"] for item in requested_properties],
                z=[0] * len(requested_properties),
                featureidkey="properties.neighborhood_id",
                colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]],
                showscale=False,
                marker={"opacity": 1, "line": {"width": 2.2, "color": "#1f77b4"}},
                customdata=[
                    [item["boundary_name"], item["official_match_status"]]
                    for item in requested_properties
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>Sınır durumu: %{customdata[1]}<extra></extra>"
                ),
                name="İncelenen mahalle sınırları",
            )
        )

    damage_colors = {
        "Destroyed": "#7f0000",
        "Damaged": "#d7301f",
        "Possibly damaged": "#fc8d59",
        "No visible damage": "#2ca25f",
        "Unknown": "#756bb1",
    }
    if show_damage:
        for grade in selected_damage:
            collection = filter_feature_collection(
                layers.damage_polygons,
                property_name="damage_grade",
                accepted_values={grade},
            )
            features = collection["features"]
            if not features:
                continue
            color = damage_colors.get(grade, "#756bb1")
            figure.add_trace(
                go.Choroplethmap(
                    geojson=collection,
                    locations=[feature["properties"]["feature_id"] for feature in features],
                    z=[1] * len(features),
                    featureidkey="properties.feature_id",
                    colorscale=[[0, color], [1, color]],
                    showscale=False,
                    marker={"opacity": 0.72, "line": {"width": 0.2, "color": color}},
                    customdata=[
                        [
                            feature["properties"]["feature_id"],
                            feature["properties"]["detection_method"],
                        ]
                        for feature in features
                    ],
                    hovertemplate=(
                        f"<b>{grade}</b><br>Copernicus kimliği: %{{customdata[0]}}"
                        "<br>Yöntem: %{customdata[1]}<extra></extra>"
                    ),
                    name=f"Copernicus · {grade}",
                )
            )

    figure.update_layout(
        map={"style": "carto-positron", "center": {"lat": 38.343, "lon": 38.288}, "zoom": 11},
        height=720,
        margin={"l": 0, "r": 0, "t": 10, "b": 0},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.01},
    )
    st.plotly_chart(figure, width="stretch")

    coverage_frame = pd.DataFrame(layers.official_coverage)
    coverage_frame["seçili_kayıt"] = sum(
        (coverage_frame[f"{person}_total"] for person in selected_persons),
        start=pd.Series(0, index=coverage_frame.index),
    )
    coverage_frame["seçili_ağır_acil_yıkık"] = sum(
        (coverage_frame[f"{person}_severe_count"] for person in selected_persons),
        start=pd.Series(0, index=coverage_frame.index),
    )
    coverage_frame["seçili_ağır_oran"] = (
        coverage_frame["seçili_ağır_acil_yıkık"]
        / coverage_frame["seçili_kayıt"].where(coverage_frame["seçili_kayıt"] > 0)
    ).fillna(0.0)
    unmapped_frame = pd.DataFrame(
        layers.unmapped_official,
        columns=[
            "person",
            "mahalle",
            "official_total",
            "severe_count",
            "severe_ratio",
            "record_geography",
        ],
    )
    unmapped_selected = unmapped_frame[unmapped_frame["person"].isin(selected_persons)].copy()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Mahalle sınırı", len(filtered_neighborhoods))
    col2.metric(
        "Haritadaki kayıt",
        f"{sum(f['properties']['display_official_total'] for f in filtered_neighborhoods):,}",
    )
    col3.metric("Kesin eşleşen kayıt", f"{int(coverage_frame['seçili_kayıt'].sum()):,}")
    col4.metric("Sınır eşleşmeyen kayıt", f"{int(unmapped_selected['official_total'].sum()):,}")
    col5.metric("Geçerli Copernicus poligonu", f"{len(damage_features):,}")
    st.caption(
        "Görüntüleme CRS'i EPSG:4326'dır. Mahalleler OSM relation kimliği ve normalize adın "
        "birlikte eşleşmesiyle bağlanmıştır. Person filtreleri yalnızca toplulaştırılmış sayıları "
        "değiştirir; tekil kayıt koordinatı üretilmez."
    )

    st.subheader("Tüm resmî mahalle kapsamı")
    st.write(
        "Aşağıdaki tablo 80 kesin ad eşleşmesini ve doğrulanan 7 yazım düzeltmesini içerir. "
        "Resmî kayıtlar yalnızca mahalle toplamı olarak tutulur."
    )
    st.dataframe(
        coverage_frame[
            [
                "mahalle",
                "coverage_group",
                "aoi_coverage_ratio",
                "seçili_kayıt",
                "seçili_ağır_acil_yıkık",
                "seçili_ağır_oran",
            ]
        ]
        .sort_values("seçili_kayıt", ascending=False)
        .style.format(
            {
                "aoi_coverage_ratio": lambda value: (
                    f"{value:.1%}" if pd.notna(value) else "değerlendirilmedi"
                ),
                "seçili_ağır_oran": "{:.1%}",
            }
        ),
        width="stretch",
    )

    with st.expander("Sınır eşleşmesi olmayan resmî kayıt grupları"):
        if unmapped_selected.empty:
            st.success("Doğrulanan yedi yazım düzeltmesinden sonra eşleşmeyen kayıt kalmadı.")
        else:
            st.warning(
                "Bu kayıtlar tabloda gösterilir ancak doğrulanmış bir mahalle sınırına veya binaya "
                "yerleştirilmez."
            )
            st.dataframe(
                unmapped_selected[
                    ["person", "mahalle", "official_total", "severe_count", "severe_ratio"]
                ]
                .sort_values("official_total", ascending=False)
                .style.format({"severe_ratio": "{:.1%}"}),
                width="stretch",
            )



def section_satellite_series() -> None:
    """Uydu · Zaman Serisi"""
    st.header("Sprint 00-13 · Sentinel-2 zamansal GeoTIFF edinimi")
    st.info(
        "Bu bölüm ekran görüntüsü kullanmaz. AOI05'i kapsayan 37SDC karesi için gerçek "
        "Sentinel-2 Level-2A üç bantlı renkli GeoTIFF edinilir. API anahtarı gerekmez. Uydu pikselleri "
        "resmî hasar kaydı veya bina düzeyi konum değildir."
    )
    plan_path = Path("data/manifests/sentinel2_temporal_plan.json")
    if not plan_path.is_file():
        st.error(f"Uydu edinim planı bulunamadı: {plan_path}")
    else:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        local_manifest_path = (
            Path(plan["output"]["destination"]) / "acquisition_manifest.json"
        )
        validated_paths = set()
        if local_manifest_path.is_file():
            local_manifest = json.loads(local_manifest_path.read_text(encoding="utf-8"))
            validated_paths = {
                item["path"]
                for item in local_manifest.get("validation", [])
                if item.get("valid") is True
            }
        scene_rows = []
        for scene in plan["scenes"]:
            local_path = Path(scene["output_path"])
            if local_path.as_posix() in validated_paths:
                local_status = "Doğrulandı"
            elif local_path.is_file():
                local_status = "GeoTIFF doğrulanacak"
            else:
                local_status = "İndirilmedi"
            scene_rows.append(
                {
                    "dönem": scene["label"],
                    "rol": scene["role"],
                    "çekim_tarihi": scene["date"],
                    "katalog_bulut_%": scene["catalog_cloud_cover_percent"],
                    "ürün": "İndirme sırasında Earth Search'ten seçilir",
                    "yerel_durum": local_status,
                }
            )
        downloaded = sum(row["yerel_durum"] != "İndirilmedi" for row in scene_rows)
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Planlanan dönem", len(scene_rows))
        col2.metric("Yerel GeoTIFF", downloaded)
        col3.metric("Çözünürlük", f"{plan['output']['pixel_size_metres']} m")
        col4.metric("Bant", len(plan["output"]["bands"]))
        st.dataframe(pd.DataFrame(scene_rows), width="stretch", hide_index=True)
        st.caption(
            f"Çıktı: {plan['output']['crs']} · tam MGRS {plan['target_mgrs']['tile']} karesi · "
            f"{', '.join(plan['output']['bands'])}. Herkese açık HTTPS kaynağı kullanılır; "
            "API anahtarı veya kullanıcı hesabı gerekmez."
        )
        st.code(
            "python scripts/11_acquire_sentinel2_temporal.py download\n"
            "python scripts/11_acquire_sentinel2_temporal.py validate",
            language="powershell",
        )



def section_v1_copernicus() -> None:
    """V1 · Copernicus"""
    st.header("V1 · Copernicus EMSR648 AOI05")
    st.write(
        "Alan, çevre ve şekil indeksi kullanılarak dört sınıflı bir mekânsal holdout "
        "deneyi yürütüldü."
    )
    v1 = reports["v1_models"].copy()
    st.dataframe(
        v1.style.format({"accuracy": "{:.3f}", "macro_f1": "{:.3f}", "weighted_f1": "{:.3f}"})
    )
    st.plotly_chart(
        px.bar(
            v1.melt(id_vars="model", value_vars=["accuracy", "macro_f1"]),
            x="model",
            y="value",
            color="variable",
            barmode="group",
            range_y=[0, 1],
            labels={"value": "Skor", "model": "Model", "variable": "Metrik"},
        ),
        width="stretch",
    )
    st.warning(
        "Yüksek accuracy çoğunluk sınıfından kaynaklanmaktadır. Düşük macro-F1, "
        "azınlık hasar sınıflarının güvenilir biçimde yakalanmadığını gösterir."
    )



def section_v2_official() -> None:
    """V2 · Resmî kayıtlar"""
    st.header("V2 · Altı sınıflı resmî hasar kaydı baseline'ı")
    st.write("Tek açıklayıcı değişken mahalle adıdır; sonuçlar stratified random split'e aittir.")
    v2 = reports["v2_models"].copy()
    st.plotly_chart(
        px.bar(
            v2.melt(id_vars="model", value_vars=["accuracy", "macro_f1"]),
            x="model",
            y="value",
            color="variable",
            barmode="group",
            range_y=[0, 1],
            labels={"value": "Skor", "model": "Model", "variable": "Metrik"},
        ),
        width="stretch",
    )
    st.dataframe(v2.style.format({"accuracy": "{:.3f}", "macro_f1": "{:.3f}"}))
    st.warning(
        "Rastgele bölme aynı mahallelerden kayıtları eğitim ve test kümelerine dağıtabilir. "
        "Bu nedenle sonuçlar görülmemiş coğrafyalara genelleme kanıtı değildir."
    )



def section_v3_spatial() -> None:
    """V3 · Mekânsal"""
    st.header("V3 · Tarihsel OSM ve mahalle düzeyi analiz")
    data = reports["v3_neighborhoods"].copy()
    min_records = st.slider("En az resmî kayıt", 0, 1_000, 100, 50)
    filtered = data[data["official_total"] >= min_records]

    st.plotly_chart(
        px.scatter(
            filtered,
            x="osm_buildings_per_km2",
            y="severe_ratio",
            size="official_total",
            hover_name="mahalle",
            color="aoi_coverage_ratio",
            labels={
                "osm_buildings_per_km2": "OSM bina yoğunluğu (km² başına)",
                "severe_ratio": "Ağır/acil/yıkık kayıt payı",
                "aoi_coverage_ratio": "AOI kapsam oranı",
            },
            title="Mahalle düzeyinde hasar payı ve tarihsel OSM kapsamı",
        ),
        width="stretch",
    )

    left, right = st.columns(2)
    left.subheader("Spearman ilişkileri")
    left.dataframe(
        reports["v3_correlations"].style.format({"spearman_rho": "{:.3f}", "p_value": "{:.4f}"})
    )
    right.subheader("Mekânsal çapraz doğrulama")
    right.dataframe(
        reports["v3_model_summary"].style.format({"mae": "{:.4f}", "weighted_mae": "{:.4f}"})
    )
    st.warning(
        "OSM bina sayısı eksik haritalamayı da ölçebilir. Mahalleler bağımsız örnekler değildir; "
        "çoklu karşılaştırma düzeltmesi uygulanmamıştır. Korelasyonlar keşifseldir ve nedensel değildir."
    )
    st.dataframe(
        filtered[
            [
                "mahalle",
                "official_total",
                "severe_ratio",
                "osm_building_count",
                "aoi_coverage_ratio",
            ]
        ].sort_values("severe_ratio", ascending=False),
        width="stretch",
    )



def section_method() -> None:
    """Yöntem"""
    st.header("Yöntem, kapsam ve yeniden üretilebilirlik")
    st.markdown(
        """
- **V1**, Copernicus poligonları üzerinde dört sınıflı bina-hasar baseline'ıdır.
- **V2**, resmî değerlendirme kayıtlarında altı sınıflı, mahalle-temelli baseline'dır.
- **V3**, 5 Şubat 2023 tarihli OSM anlık görüntüsünden türetilen mahalle özelliklerini kullanır.
- V1, V2 ve V3 farklı hedef, örneklem birimi ve doğrulama düzenlerine sahiptir; skorları doğrudan karşılaştırılamaz.
- Resmî kayıtlar tekil fiziksel binalarla doğrulanmış bire bir eşleşme değildir.
- Haritadaki resmî hasar değerleri yalnızca mahalle düzeyi toplulaştırmalardır; bina koordinatı değildir.
- Ham/işlenmiş coğrafi verilerin bir kısmı lisans, boyut ve yeniden üretilebilirlik nedenleriyle git'te tutulmaz.
- Arayüz yalnızca sürümlenmiş rapor çıktılarını okur; model çıkarımı veya bina düzeyi risk tahmini yapmaz.
"""
    )



# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------

NAVIGATION = {
    "Ana Sayfa": {"icon": ":material/home:", "pages": {"Ana Sayfa": section_home}},
    "Harita Analizi": {
        "icon": ":material/map:",
        "pages": {
            "İnteraktif Harita": section_interactive_map,
            "Gerçek Hasar Haritası": section_real_damage_map,
            "Harita · Katmanlar": section_map_layers,
        },
    },
    "Model Tahmini": {
        "icon": ":material/model_training:",
        "pages": {
            "Bina Tahmin Haritası": section_prediction_map,
            "Model performansı": section_model_performance,
        },
    },
    "Veri Setleri": {
        "icon": ":material/database:",
        "pages": {
            "Veri kaynakları": section_sources,
            "V1 · Copernicus": section_v1_copernicus,
            "V2 · Resmî kayıtlar": section_v2_official,
        },
    },
    "İstatistikler": {
        "icon": ":material/bar_chart:",
        "pages": {
            "Mekânsal Analiz ve Mahalle Karşılaştırması": section_spatial,
            "V3 · Mekânsal": section_v3_spatial,
        },
    },
    "Karşılaştırma": {
        "icon": ":material/compare:",
        "pages": {
            "2022–2023 Değişim Analizi": section_change_2022_2023,
            "2023–2026 Yeniden Yapılanma": section_reconstruction,
            "Uydu · Zaman Serisi": section_satellite_series,
        },
    },
    "Rapor & İndirme": {"icon": ":material/download:",
                        "pages": {"Rapor & İndirme": section_reports}},
    "Yöntem": {"icon": ":material/menu_book:", "pages": {"Yöntem": section_method}},
}

with st.sidebar:
    menu = st.radio(
        "Menü",
        list(NAVIGATION),
        format_func=lambda name: f"{NAVIGATION[name]['icon']} {name}",
        label_visibility="collapsed",
        key="menu",
    )
    st.divider()
    st.caption(
        "Araştırma amaçlıdır; resmî hasar veya bina güvenliği kararı değildir. "
        "Gösterilen ilişkiler nedensellik kanıtlamaz."
    )

pages = NAVIGATION[menu]["pages"]
if len(pages) > 1:
    page = st.radio("Bölüm", list(pages), horizontal=True, key=f"page_{menu}")
else:
    page = next(iter(pages))
pages[page]()
