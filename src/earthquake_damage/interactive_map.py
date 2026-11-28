"""Sprint 00-22 — interactive map, period panel and building detail data.

``prepare`` joins, for each of the 3,617 EMSR648 buildings, everything the detail panel
shows: observed EMSR648 grade, the exploratory model prediction, neighbourhood and district,
2022→2023 spectral change cover and the 2023→2026 OSM reconstruction status. ``render`` is
the Streamlit map: satellite or street basemap, GIS layer toggles, the 2022/2023/2026 period,
side-by-side comparison and the building panel.

The 2026 status needs the git-ignored 2023 OSM snapshot; without it the column says so
instead of guessing.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

RECONSTRUCTION_STATUS_TR = {
    "none_removed": "2026'ya kadar kaldırılan OSM binası yok",
    "some_removed": "OSM binalarının bir kısmı kaldırılmış (<%50)",
    "mostly_removed": "OSM binalarının çoğu kaldırılmış (≥%50)",
    "no_osm_footprint": "2023 OSM'de içinde bina yok",
    "snapshot_unavailable": "OSM kesiti yerelde yok",
}
DAMAGE_COLORS = {
    "No visible damage": "#3B82F6",
    "Possibly damaged": "#EAB308",
    "Damaged": "#F97316",
    "Destroyed": "#EF4444",
}
DAMAGE_LABELS_TR = {
    "No visible damage": "Görünür hasar yok",
    "Possibly damaged": "Olası hasarlı",
    "Damaged": "Hasarlı",
    "Destroyed": "Yıkılmış",
}
PREDICTION_TO_GRADE = {
    "no_visible_damage": "No visible damage",
    "possibly_damaged": "Possibly damaged",
    "damaged": "Damaged",
    "destroyed": "Destroyed",
}
RECON_COLORS = {
    "removed_candidate": "#EF4444",
    "new_candidate": "#22C55E",
    "modified_candidate": "#EAB308",
    "uncertain": "#94A3B8",
}
# Layers that describe each period; the map offers only these for the chosen period.
PERIOD_LAYERS = {
    "2022": ("neighborhoods", "spectral_2022_2023", "osm_2022"),
    "2023": ("neighborhoods", "official", "hotspots", "emsr648", "predictions", "osm_2023"),
    "2026": ("neighborhoods", "reconstruction", "osm_2026"),
}
LAYER_LABELS = {
    "neighborhoods": "Mahalle sınırları",
    "official": "Resmî ağır hasar oranı (mahalle)",
    "hotspots": "Sıcak noktalar (Gi*, resmî oran)",
    "emsr648": "Bina hasar sınıfı (EMSR648)",
    "predictions": "Model tahmini",
    "spectral_2022_2023": "Spektral değişim 2022→2023",
    "reconstruction": "Yeniden yapılanma 2023→2026",
    "osm_2022": "OSM binaları 2022",
    "osm_2023": "OSM binaları 2023",
    "osm_2026": "OSM binaları 2026",
}
DEFAULT_LAYERS = {
    "2022": ("neighborhoods", "spectral_2022_2023"),
    "2023": ("neighborhoods", "emsr648"),
    "2026": ("neighborhoods", "reconstruction"),
}


def available_layers(period: str) -> tuple[str, ...]:
    return PERIOD_LAYERS[period]


def count_points_within(polygons, footprints) -> np.ndarray:
    """Number of footprints whose representative point lies inside each polygon."""
    import geopandas as gpd

    if len(footprints) == 0:
        return np.zeros(len(polygons), dtype=int)
    points = gpd.GeoDataFrame(geometry=footprints.geometry.representative_point(),
                              crs=footprints.crs)
    joined = gpd.sjoin(points, polygons[["geometry"]].reset_index(names="p"), predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]  # a point counts once
    counts = joined.groupby("p").size()
    result = np.zeros(len(polygons), dtype=int)
    result[counts.index.to_numpy()] = counts.to_numpy()
    return result


def reconstruction_status(osm_2023: np.ndarray, removed: np.ndarray) -> np.ndarray:
    """Summarise 2023→2026 change inside an EMSR648 polygon from footprint counts."""
    share = np.divide(removed, osm_2023, out=np.zeros(len(osm_2023)), where=osm_2023 > 0)
    return np.select(
        [osm_2023 == 0, removed == 0, share < 0.5],
        ["no_osm_footprint", "none_removed", "some_removed"],
        default="mostly_removed",
    ).astype(object)


def spectral_cover(buildings, spectral) -> np.ndarray:
    """Share of each building's area covered by 2022→2023 spectral candidate polygons."""
    import geopandas as gpd

    if spectral.empty:
        return np.zeros(len(buildings))
    pieces = gpd.overlay(
        buildings[["geometry"]].reset_index(names="b"), spectral[["geometry"]],
        how="intersection", keep_geom_type=True,
    )
    covered = pieces.assign(a=pieces.geometry.area).groupby("b")["a"].sum()
    areas = buildings.geometry.area.to_numpy()
    result = np.zeros(len(buildings))
    result[covered.index.to_numpy()] = covered.to_numpy() / areas[covered.index.to_numpy()]
    return np.clip(result, 0, 1)


def prepare(root: Path, config: dict) -> dict:
    """Write ``building_details.csv`` for the building panel and the map's point layer."""
    import geopandas as gpd
    import pandas as pd

    root = Path(root)
    metric = config["metric_crs"]
    buildings = gpd.read_parquet(root / config["buildings"]).to_crs(metric).reset_index(drop=True)
    predictions = gpd.read_file(root / config["predictions"]).drop(columns="geometry")
    districts = pd.read_csv(root / config["districts"])[["mahalle", "district"]]
    spectral = gpd.read_file(root / config["spectral_change_2022_2023"]).to_crs(metric)
    reconstruction = gpd.read_parquet(root / config["reconstruction_map"])
    reconstruction = reconstruction[reconstruction["layer"] == "osm_footprint"]

    removed = reconstruction[reconstruction["reconstruction_class"] == "removed_candidate"]
    new = reconstruction[reconstruction["reconstruction_class"] == "new_candidate"]
    removed_counts = count_points_within(buildings, removed.to_crs(metric))
    new_counts = count_points_within(buildings, new.to_crs(metric))
    snapshot = root / config["osm_post_event_snapshot"]
    if snapshot.exists():
        osm = gpd.read_file(snapshot).to_crs(metric)
        osm_counts = count_points_within(buildings, osm)
        status = reconstruction_status(osm_counts, removed_counts)
        snapshot_hash = __import__("hashlib").sha256(snapshot.read_bytes()).hexdigest()
    else:
        osm_counts = np.full(len(buildings), -1)
        status = np.array(["snapshot_unavailable"] * len(buildings), dtype=object)
        snapshot_hash = None

    centroids = buildings.geometry.representative_point().to_crs(4326)
    table = pd.DataFrame({
        "feature_id": buildings["feature_id"],
        "mahalle": buildings["mahalle"].fillna("unknown"),
        "damage_grade": buildings["damage_grade"],
        "area_m2": buildings["area_m2"].round(1),
        "perimeter_m": buildings["perimeter_m"].round(1),
        "lat": centroids.y.round(6),
        "lon": centroids.x.round(6),
        "spectral_cover_2022_2023": np.round(spectral_cover(buildings, spectral), 3),
        "osm_buildings_2023": osm_counts,
        "removed_by_2026": removed_counts,
        "new_by_2026": new_counts,
        "reconstruction_status": status,
    })
    table = table.merge(districts, on="mahalle", how="left")
    table["district"] = table["district"].fillna("unknown")
    keep = ["feature_id", "predicted_damage", "confidence", "low_confidence",
            "probability_no_visible_damage", "probability_possibly_damaged",
            "probability_damaged", "probability_destroyed"]
    table = table.merge(predictions[keep], on="feature_id", how="left", validate="one_to_one")
    if table["predicted_damage"].isna().any():
        raise ValueError("Some buildings have no prediction")
    float_columns = [c for c in keep if c.startswith("probability") or c == "confidence"]
    table[float_columns] = table[float_columns].round(4)

    output = root / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    path = output / "building_details.csv"
    table.to_csv(path, index=False, encoding="utf-8")
    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "buildings": len(table),
        "reconstruction_status_counts": table["reconstruction_status"].value_counts().to_dict(),
        "buildings_with_spectral_cover": int((table["spectral_cover_2022_2023"] > 0).sum()),
        "osm_post_event_snapshot_sha256": snapshot_hash,
        "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
    }
    (output / "building_details.source.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary


def detail_rows(building: dict) -> list[tuple[str, str]]:
    """Label/value pairs for the building panel, in display order."""
    def pct(value) -> str:
        if value is None or (isinstance(value, float) and np.isnan(value)):
            return "—"
        return "%" + f"{float(value) * 100:.0f}"

    grade = building.get("damage_grade")
    predicted = PREDICTION_TO_GRADE.get(building.get("predicted_damage"), "")
    confidence = building.get("confidence")
    low = bool(building.get("low_confidence"))
    return [
        ("Poligon ID", str(building.get("feature_id"))),
        ("İlçe", str(building.get("district"))),
        ("Mahalle", str(building.get("mahalle"))),
        ("EMSR648 hasar sınıfı", DAMAGE_LABELS_TR.get(grade, str(grade))),
        ("Model tahmini", DAMAGE_LABELS_TR.get(predicted, "—")),
        ("Model güveni", f"{float(confidence):.2f}".replace(".", ",")
         + (" · düşük güven" if low else "") if confidence is not None else "—"),
        ("Poligon alanı", f"{float(building.get('area_m2', 0)):,.0f} m²".replace(",", ".")),
        ("Çevre", f"{float(building.get('perimeter_m', 0)):.0f} m"),
        ("Spektral değişim 2022→2023", pct(building.get("spectral_cover_2022_2023"))),
        ("2023 OSM binası (içinde)", _count(building.get("osm_buildings_2023"))),
        ("2026'ya kadar kaldırılan / yeni", f"{_count(building.get('removed_by_2026'))} / "
         f"{_count(building.get('new_by_2026'))}"),
        ("2023→2026 durumu", RECONSTRUCTION_STATUS_TR.get(
            building.get("reconstruction_status"), str(building.get("reconstruction_status")))),
    ]


def _count(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)) or int(value) < 0:
        return "—"
    return str(int(value))


# ---------------------------------------------------------------------------
# Streamlit rendering
# ---------------------------------------------------------------------------

BASEMAPS = {
    "Uydu": "satellite",
    "Sokak": "open-street-map",
    "Koyu": "carto-darkmatter",
}
SATELLITE_TILES = (
    "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
)
PATHS = {
    "neighborhoods": "data/dashboard/sprint_00-20/neighborhood_spatial_analysis.geojson",
    "emsr648": "data/dashboard/sprint_00-12/copernicus_damage_polygons.geojson",
    "details": "data/dashboard/sprint_00-22/building_details.csv",
    "spectral_2022_2023": "data/dashboard/sprint_00-18/pre_post_change_map.geojson",
    "reconstruction": "data/dashboard/sprint_00-19/reconstruction_change_map.parquet",
    "osm_2022": "data/external/building_change/buildings_2022.geojson",
    "osm_2023": "data/external/reconstruction/osm/buildings_post_event.geojson",
    "osm_2026": "data/external/reconstruction/osm/buildings_current.geojson",
}
# Layers too dense to draw for the whole city; they need a neighbourhood focus.
FOCUS_ONLY = {"spectral_2022_2023", "osm_2022", "osm_2023", "osm_2026"}
HOTSPOT_COLORS = {
    "hot_99": "#B2182B", "hot_95": "#EF8A62", "hot_90": "#FDDBC7", "cold_90": "#D1E5F0",
    "cold_95": "#67A9CF", "cold_99": "#2166AC",
}


def map_layout(basemap: str, center: dict, zoom: float, height: int) -> dict:
    style = BASEMAPS[basemap]
    map_config = {"center": center, "zoom": zoom}
    if style == "satellite":
        map_config.update(style="white-bg", layers=[
            {"sourcetype": "raster", "source": [SATELLITE_TILES], "below": "traces"}
        ])
    else:
        map_config["style"] = style
    return {
        "map": map_config, "height": height, "margin": {"l": 0, "r": 0, "t": 0, "b": 0},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "legend": {"orientation": "h", "y": 1.0, "yanchor": "bottom",
                   "font": {"color": "#E6EDF6", "size": 11}, "bgcolor": "rgba(11,18,32,0.6)"},
        "uirevision": "keep",
    }


def focus_view(bounds) -> tuple[dict, float]:
    """Centre and an approximate zoom that fits WGS84 ``bounds`` (west, south, east, north)."""
    west, south, east, north = bounds
    span = max(east - west, (north - south) * 1.3, 1e-4)
    zoom = float(np.clip(np.log2(360 / span) - 0.6, 10, 17.5))
    return {"lat": (south + north) / 2, "lon": (west + east) / 2}, zoom


def categorical_traces(frame, column: str, colors: dict, labels: dict | None = None,
                       opacity: float = 0.75, hover_columns: tuple = ()) -> list:
    """One Choroplethmap trace per category so each has its own legend entry."""
    import plotly.graph_objects as go

    traces = []
    for category, color in colors.items():
        subset = frame[frame[column] == category]
        if subset.empty:
            continue
        geojson = json.loads(subset[["geometry"]].reset_index(drop=True).to_json())
        hover = [
            "<br>".join(f"{c}: {row[c]}" for c in hover_columns) if hover_columns else ""
            for _, row in subset.iterrows()
        ]
        traces.append(go.Choroplethmap(
            geojson=geojson, locations=[str(i) for i in range(len(subset))],
            featureidkey="id", z=[1] * len(subset),
            colorscale=[[0, color], [1, color]], showscale=False, marker_opacity=opacity,
            marker_line_width=0.4, marker_line_color="#0B1220",
            name=f"{(labels or {}).get(category, category)} ({len(subset):,})".replace(",", "."),
            showlegend=True, text=hover, hovertemplate="%{text}<extra></extra>",
        ))
    return traces


def render(root: Path, period: str, key: str = "imap") -> None:  # pragma: no cover - UI
    import geopandas as gpd
    import pandas as pd
    import plotly.graph_objects as go
    import streamlit as st

    root = Path(root)

    @st.cache_resource(show_spinner="Katman yükleniyor…")
    def load_layer(name: str):
        path = root / PATHS[name]
        if not path.exists():
            return None
        frame = (gpd.read_parquet(path) if path.suffix == ".parquet" else gpd.read_file(path))
        return frame.to_crs(4326)

    @st.cache_data(show_spinner=False)
    def load_details() -> pd.DataFrame | None:
        path = root / PATHS["details"]
        return pd.read_csv(path) if path.exists() else None

    hoods = load_layer("neighborhoods")
    details = load_details()
    if hoods is None or details is None:
        st.info("Harita girdileri eksik: `python scripts/19_analyze_spatial_neighborhoods.py` ve "
                "`python scripts/21_prepare_interactive_map.py` çalıştırın.")
        return

    with st.sidebar:
        st.subheader("İnteraktif harita")
        basemap = st.radio("Altlık", list(BASEMAPS), horizontal=True, key=f"{key}_basemap")
        focus = st.selectbox("Mahalle odağı", ["Tüm çalışma alanı", *sorted(hoods["mahalle"])],
                             key=f"{key}_focus")
        layers = [
            layer for layer in available_layers(period)
            if st.checkbox(LAYER_LABELS[layer], value=layer in DEFAULT_LAYERS[period],
                           key=f"{key}_{period}_{layer}")
        ]

    focus_geometry = None
    if focus != "Tüm çalışma alanı":
        focus_geometry = hoods.loc[hoods["mahalle"] == focus, "geometry"].iloc[0]
        center, zoom = focus_view(focus_geometry.bounds)
    else:
        center, zoom = focus_view(hoods.total_bounds)

    def clip(frame):
        if frame is None or focus_geometry is None:
            return frame
        return frame[frame.intersects(focus_geometry)]

    def traces_for(layer: str, which_period: str) -> tuple[list, str | None]:
        """Plotly traces for one layer, or a note explaining why it is not drawn."""
        if layer in FOCUS_ONLY and focus_geometry is None:
            return [], f"{LAYER_LABELS[layer]}: yoğun katman, bir mahalle seçince çizilir."
        if layer == "neighborhoods":
            frame = clip(hoods)
            geojson = json.loads(frame[["geometry"]].reset_index(drop=True).to_json())
            return [go.Choroplethmap(
                geojson=geojson, locations=[str(i) for i in range(len(frame))],
                featureidkey="id", z=[0] * len(frame), showscale=False,
                colorscale=[[0, "rgba(255,255,255,0.02)"], [1, "rgba(255,255,255,0.02)"]],
                marker_line_width=1.2, marker_line_color="#E6EDF6", name="Mahalle sınırları",
                text=list(frame["mahalle"]), hovertemplate="%{text}<extra></extra>",
                showlegend=False,
            )], None
        if layer == "official":
            frame = clip(hoods)
            geojson = json.loads(frame[["geometry"]].reset_index(drop=True).to_json())
            return [go.Choroplethmap(
                geojson=geojson, locations=[str(i) for i in range(len(frame))],
                featureidkey="id", z=frame["official_severe_ratio"], colorscale="YlOrRd",
                zmin=0, zmax=1, marker_opacity=0.6, marker_line_width=0.5,
                colorbar={"title": "Ağır oran", "thickness": 10, "x": 0.01,
                          "tickfont": {"color": "#E6EDF6"}},
                text=[f"{m}: {v:.2f}" for m, v in
                      zip(frame["mahalle"], frame["official_severe_ratio"], strict=True)],
                hovertemplate="%{text}<extra></extra>", name="Resmî ağır hasar oranı",
            )], None
        if layer == "hotspots":
            frame = clip(hoods)
            from earthquake_damage.spatial_analysis import HOTSPOT_LABELS_TR
            return categorical_traces(frame, "official_severe_ratio__hotspot", HOTSPOT_COLORS,
                                      HOTSPOT_LABELS_TR, 0.65, ("mahalle",)), None
        if layer in {"emsr648", "predictions"}:
            frame = clip(load_layer("emsr648"))
            frame = frame.merge(details[["feature_id", "predicted_damage"]], on="feature_id")
            if layer == "predictions":
                frame = frame.assign(grade=frame["predicted_damage"].map(PREDICTION_TO_GRADE))
            else:
                frame = frame.assign(grade=frame["damage_grade"])
            prefix = "Tahmin: " if layer == "predictions" else ""
            labels = {k: prefix + v for k, v in DAMAGE_LABELS_TR.items()}
            return categorical_traces(frame, "grade", DAMAGE_COLORS, labels, 0.8,
                                      ("feature_id", "grade")), None
        if layer == "reconstruction":
            frame = clip(load_layer("reconstruction"))
            frame = frame[frame["layer"] == "osm_footprint"]
            from earthquake_damage.reconstruction_change_analysis import CLASS_LABELS_TR
            return categorical_traces(frame, "reconstruction_class", RECON_COLORS,
                                      CLASS_LABELS_TR, 0.8, ("unit_id", "evidence")), None
        if layer == "spectral_2022_2023":
            frame = clip(load_layer("spectral_2022_2023"))
            frame = frame.assign(kind="spectral")
            return categorical_traces(frame, "kind", {"spectral": "#A855F7"},
                                      {"spectral": "Spektral aday alan"}, 0.45), None
        if layer.startswith("osm_"):
            frame = load_layer(layer)
            if frame is None:
                return [], f"{LAYER_LABELS[layer]}: yerel OSM kesiti yok (Git dışı veri)."
            frame = clip(frame).assign(kind=layer)
            return categorical_traces(frame, "kind", {layer: "#CBD5E1"},
                                      {layer: LAYER_LABELS[layer]}, 0.55), None
        return [], None

    def building_points(selected: str | None):
        """Clickable centroids for EMSR648 polygons inside the current view."""
        frame = details
        if focus_geometry is not None:
            frame = frame[frame["mahalle"] == focus]
        colors = [DAMAGE_COLORS.get(g, "#94A3B8") for g in frame["damage_grade"]]
        sizes = [13 if f == selected else 6 for f in frame["feature_id"]]
        return go.Scattermap(
            lat=frame["lat"], lon=frame["lon"], mode="markers",
            marker={"size": sizes, "color": colors, "opacity": 0.9},
            customdata=frame["feature_id"], name="Poligon merkezleri (tıklanabilir)",
            text=frame["feature_id"], hovertemplate="%{text}<extra></extra>",
        )

    def draw(which_period: str, chosen_layers: list[str], height: int, chart_key: str,
             selected: str | None = None, clickable: bool = False):
        figure = go.Figure()
        notes = []
        for layer in chosen_layers:
            traces, note = traces_for(layer, which_period)
            for trace in traces:
                figure.add_trace(trace)
            if note:
                notes.append(note)
        if clickable:
            figure.add_trace(building_points(selected))
        figure.update_layout(**map_layout(basemap, center, zoom, height))
        if clickable:
            event = st.plotly_chart(figure, width="stretch", key=chart_key,
                                    on_select="rerun", selection_mode=("points",))
        else:  # a plain chart returns a DeltaGenerator, not a selection event
            st.plotly_chart(figure, width="stretch", key=chart_key)
            event = None
        for note in notes:
            st.caption(note)
        return event

    mode = st.radio("Görünüm", ["Tek harita", "Yan yana karşılaştırma"], horizontal=True,
                    key=f"{key}_mode")
    selected_key = f"{key}_selected"

    if mode == "Tek harita":
        map_col, panel_col = st.columns([3, 1.25], gap="medium")
        with map_col:
            event = draw(period, layers, 640, f"{key}_single",
                         st.session_state.get(selected_key), clickable=period == "2023")
            points = selected_points(event)
            if points and points[0].get("customdata"):
                st.session_state[selected_key] = points[0]["customdata"]
            if basemap == "Uydu":
                st.caption("Uydu altlığı: Esri, Maxar, Earthstar Geographics, and the GIS User "
                           "Community · yalnız görsel bağlam.")
        with panel_col:
            render_building_panel(details, focus, selected_key, key)
    else:
        options = list(PERIOD_LAYERS)
        comparison = st.radio(
            "Karşılaştırma", ["Dönemler", "Gerçek ↔ Tahmin (2023)"], horizontal=True,
            key=f"{key}_comparison",
        )
        left, right = st.columns(2, gap="small")
        if comparison == "Dönemler":
            with left:
                left_period = st.selectbox("Sol dönem", options, index=1, key=f"{key}_left")
                draw(left_period, list(DEFAULT_LAYERS[left_period]) + _osm_layer(left_period),
                     520, f"{key}_left_map")
            with right:
                right_period = st.selectbox("Sağ dönem", options, index=2, key=f"{key}_right")
                draw(right_period, list(DEFAULT_LAYERS[right_period]) + _osm_layer(right_period),
                     520, f"{key}_right_map")
            st.caption("İki harita aynı merkez ve yakınlaştırmayı kullanır. OSM bina katmanları "
                       "yalnız bir mahalle seçildiğinde çizilir.")
        else:
            with left:
                st.markdown("**Gerçek · EMSR648**")
                draw("2023", ["neighborhoods", "emsr648"], 520, f"{key}_truth")
            with right:
                st.markdown("**Tahmin · random forest (keşif amaçlı)**")
                draw("2023", ["neighborhoods", "predictions"], 520, f"{key}_pred")
            st.caption("Model, aynı EMSR648 poligonlarında eğitildi; bu görünüm örneklem içi "
                       "uyumu gösterir, doğrulama değildir.")


def selected_points(event) -> list[dict]:
    """Points from a Streamlit Plotly selection event; empty when nothing is selected."""
    if not event:
        return []
    selection = event.get("selection") if hasattr(event, "get") else None
    return list((selection or {}).get("points", []))


def _osm_layer(period: str) -> list[str]:
    return [f"osm_{period}"]


def render_building_panel(details, focus: str, selected_key: str,
                          key: str) -> None:  # pragma: no cover - UI
    import plotly.graph_objects as go
    import streamlit as st

    with st.container(border=True):
        st.markdown('<div class="panel-title">Seçili yapı alanı</div>', unsafe_allow_html=True)
        pool = details if focus == "Tüm çalışma alanı" else details[details["mahalle"] == focus]
        if pool.empty:
            st.caption("Bu mahallede EMSR648 poligonu yok.")
            return
        ids = list(pool.sort_values(["damage_grade", "feature_id"])["feature_id"])
        current = st.session_state.get(selected_key)
        index = ids.index(current) if current in ids else 0
        chosen = st.selectbox("Poligon", ids, index=index, key=f"{key}_picker",
                              help="Haritada 2023 döneminde bir noktaya tıklayarak da seçilir.")
        st.session_state[selected_key] = chosen
        building = details.set_index("feature_id").loc[chosen].to_dict()
        building["feature_id"] = chosen
        rows = detail_rows(building)
        st.markdown(
            "<table style='width:100%;font-size:0.86rem'>"
            + "".join(f"<tr><td style='color:#93A3BD;padding:2px 6px 2px 0'>{label}</td>"
                      f"<td style='padding:2px 0'><b>{value}</b></td></tr>"
                      for label, value in rows)
            + "</table>",
            unsafe_allow_html=True,
        )
        probabilities = {
            DAMAGE_LABELS_TR[PREDICTION_TO_GRADE[name]]:
                building[f"probability_{name}"]
            for name in PREDICTION_TO_GRADE
        }
        figure = go.Figure(go.Bar(
            x=list(probabilities.values()), y=list(probabilities), orientation="h",
            marker_color=[DAMAGE_COLORS[PREDICTION_TO_GRADE[n]] for n in PREDICTION_TO_GRADE],
        ))
        figure.update_layout(height=170, margin={"l": 0, "r": 0, "t": 20, "b": 0},
                             paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                             font={"color": "#E6EDF6", "size": 11},
                             title={"text": "Model sınıf olasılıkları", "font": {"size": 12}},
                             xaxis={"range": [0, 1]})
        st.plotly_chart(figure, width="stretch", key=f"{key}_probabilities")
        st.caption("EMSR648 poligonları yapı alanlarıdır; birden fazla bina içerebilir. "
                   "Olasılıklar kalibre edilmemiştir.")
