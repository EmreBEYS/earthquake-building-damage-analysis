"""Sprint 00-11 Streamlit research dashboard."""

from __future__ import annotations

import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from earthquake_damage.dashboard_data import (
    DashboardDataError,
    aggregate_damage_distribution,
    load_dashboard_reports,
)
from earthquake_damage.geospatial_layers import (
    GeospatialLayerError,
    filter_feature_collection,
    load_map_layers,
)

st.set_page_config(
    page_title="Malatya Deprem Hasar Araştırması",
    page_icon="🔬",
    layout="wide",
)

st.title("Malatya Deprem Hasar Araştırması")
st.caption("Sprint 00-12 · doğrulanmış deney çıktıları ve coğrafi katmanlar")

st.warning(
    "Bu arayüz araştırma amaçlıdır. Sonuçlar bina güvenliği, tahliye, güçlendirme veya "
    "resmî hasar kararı için kullanılamaz. Gösterilen ilişkiler nedensellik kanıtlamaz."
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

page = st.sidebar.radio(
    "Bölüm",
    [
        "Genel bakış",
        "Harita · Katmanlar",
        "V1 · Copernicus",
        "V2 · Resmî kayıtlar",
        "V3 · Mekânsal",
        "Yöntem",
    ],
)

if page == "Genel bakış":
    damage = aggregate_damage_distribution(reports["damage_distribution"])
    neighborhoods = reports["v3_neighborhoods"]
    total_records = int(damage["records"].sum())

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Resmî kayıt", f"{total_records:,}")
    col2.metric("Copernicus poligonu", "3.619")
    col3.metric("Tarihsel OSM binası", "3.545")
    col4.metric("Yüksek kapsamlı mahalle", f"{len(neighborhoods)}")

    st.plotly_chart(
        px.bar(
            damage,
            x="records",
            y="damage_class",
            orientation="h",
            labels={"records": "Kayıt", "damage_class": "Hasar sınıfı"},
            title="Resmî hasar kayıtlarının sınıf dağılımı",
        ),
        use_container_width=True,
    )
    st.caption(
        "46.563 kayıt, gözlenen tüm bina stokunun rastgele örneklemi değildir. "
        "Sınıf dengesizliği ve değerlendirme kapsamı model metriklerini etkiler."
    )

elif page == "Harita · Katmanlar":
    st.header("AOI05 coğrafi katmanları")
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
    damage_features = layers.damage_polygons["features"]
    damage_grades = sorted({feature["properties"]["damage_grade"] for feature in damage_features})

    with st.sidebar:
        st.subheader("Harita filtreleri")
        show_official = st.checkbox("Mahalle resmî hasar oranı", value=True)
        show_damage = st.checkbox("Copernicus hasar poligonları", value=True)
        min_records = st.slider("En az resmî kayıt", 0, 3_000, 100, 50)
        selected_damage = st.multiselect(
            "Copernicus hasar sınıfı", damage_grades, default=damage_grades
        )
        available_names = sorted(
            feature["properties"]["mahalle"]
            for feature in neighborhood_features
            if feature["properties"]["official_total"] >= min_records
        )
        selected_names = st.multiselect("Mahalle", available_names, default=available_names)

    visible_neighborhoods = {
        feature["properties"]["neighborhood_id"]
        for feature in neighborhood_features
        if feature["properties"]["official_total"] >= min_records
        and feature["properties"]["mahalle"] in selected_names
    }
    neighborhood_geojson = filter_feature_collection(
        layers.neighborhoods,
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
                z=[item["severe_ratio"] for item in properties],
                featureidkey="properties.neighborhood_id",
                colorscale="YlOrRd",
                zmin=0,
                zmax=0.6,
                marker={"opacity": 0.5, "line": {"width": 1.5, "color": "#202020"}},
                colorbar={"title": "Ağır/acil/yıkık<br>kayıt payı"},
                customdata=[
                    [item["mahalle"], item["official_total"], item["severe_count"]]
                    for item in properties
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>Resmî kayıt: %{customdata[1]:,}"
                    "<br>Ağır/acil/yıkık: %{customdata[2]:,}<br>Pay: %{z:.1%}<extra></extra>"
                ),
                name="Mahalle toplamları",
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
    st.plotly_chart(figure, use_container_width=True)

    map_validation = layers.validation["checks"]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Mahalle sınırı", len(filtered_neighborhoods))
    col2.metric(
        "Mahalle resmî kaydı",
        f"{sum(f['properties']['official_total'] for f in filtered_neighborhoods):,}",
    )
    col3.metric("Geçerli Copernicus poligonu", f"{len(damage_features):,}")
    col4.metric(
        "Geometri dışlanan",
        map_validation["copernicus_damage_polygons"]["excluded_non_polygonal_or_empty"],
    )
    st.caption(
        "Görüntüleme CRS'i EPSG:4326'dır. Mahalleler OSM relation kimliği ve normalize adın "
        "birlikte eşleşmesiyle bağlanmıştır. Copernicus kaynak paketindeki iki boş/poligonal "
        "olmayan onarılamaz geometri harita katmanından dışlanmış ve doğrulama raporuna yazılmıştır."
    )

elif page == "V1 · Copernicus":
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
        use_container_width=True,
    )
    st.warning(
        "Yüksek accuracy çoğunluk sınıfından kaynaklanmaktadır. Düşük macro-F1, "
        "azınlık hasar sınıflarının güvenilir biçimde yakalanmadığını gösterir."
    )

elif page == "V2 · Resmî kayıtlar":
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
        use_container_width=True,
    )
    st.dataframe(v2.style.format({"accuracy": "{:.3f}", "macro_f1": "{:.3f}"}))
    st.warning(
        "Rastgele bölme aynı mahallelerden kayıtları eğitim ve test kümelerine dağıtabilir. "
        "Bu nedenle sonuçlar görülmemiş coğrafyalara genelleme kanıtı değildir."
    )

elif page == "V3 · Mekânsal":
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
        use_container_width=True,
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
        use_container_width=True,
    )

else:
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
