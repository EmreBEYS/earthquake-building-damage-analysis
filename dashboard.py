"""Sprint 00-11 Streamlit research dashboard."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
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
st.caption("Sprint 00-13 · doğrulanmış coğrafi katmanlar ve zamansal uydu edinimi")

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
        "Uydu · Zaman Serisi",
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
    st.plotly_chart(figure, use_container_width=True)

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
        use_container_width=True,
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
                use_container_width=True,
            )

elif page == "Uydu · Zaman Serisi":
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
        st.dataframe(pd.DataFrame(scene_rows), use_container_width=True, hide_index=True)
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
