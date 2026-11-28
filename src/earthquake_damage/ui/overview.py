"""Data behind the dashboard home page and source indicators (Sprint 00-21).

Everything here is computed from committed project outputs; no number on the home page
is typed by hand.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

# Official Ministry damage classes, in severity order, with display labels and colours.
OFFICIAL_CLASSES = (
    ("no_damage", "Hasarsız", "#3B82F6"),
    ("slight_damage", "Az hasarlı", "#22C55E"),
    ("moderate_damage", "Orta hasarlı", "#EAB308"),
    ("heavy_damage", "Ağır hasarlı", "#F97316"),
    ("urgent_demolition", "Acil yıkılacak", "#EF4444"),
    ("destroyed", "Yıkık", "#991B1B"),
)

PERIODS = {
    "2022": "2022 (Deprem Öncesi)",
    "2023": "2023 (Deprem Sonrası)",
    "2026": "2026 (Güncel)",
}

# Every dataset the dashboard reads, with its role and terms. ``path`` is checked at runtime.
DATA_SOURCES = {
    "official": {
        "name": "Bakanlık hasar tespit kayıtları",
        "role": "46.563 kayıt; mahalle düzeyinde, koordinatsız",
        "sprint": "00-15",
        "path": "data/dashboard/sprint_00-15/official_neighborhood_statistics.csv",
        "terms": "Kamu kaydı; yeniden kullanım koşulları doğrulanmadı",
    },
    "emsr648": {
        "name": "Copernicus EMS EMSR648 AOI05",
        "role": "3.617 bina poligonu; görüntüden hasar yorumu",
        "sprint": "00-12",
        "path": "data/dashboard/sprint_00-12/copernicus_damage_polygons.geojson",
        "terms": "Copernicus EMS koşulları; atıf gerekli",
    },
    "neighborhoods": {
        "name": "Mahalle sınırları (OSM)",
        "role": "87 gözden geçirilmiş mahalle",
        "sprint": "00-12",
        "path": "data/dashboard/sprint_00-12/aoi05_neighborhoods.geojson",
        "terms": "ODbL 1.0; © OpenStreetMap katkıcıları",
    },
    "districts": {
        "name": "İlçe sınırları (geoBoundaries ADM2)",
        "role": "Battalgazi ve Yeşilyurt; mahalle–ilçe eşleşmesi",
        "sprint": "00-21",
        "path": "data/dashboard/sprint_00-21/neighborhood_districts.csv",
        "terms": "ODbL 1.0 (geoBoundaries / OSM Boundaries)",
    },
    "predictions": {
        "name": "Model tahminleri (random forest)",
        "role": "Keşif amaçlı; mekânsal macro-F1 0,24",
        "sprint": "00-17",
        "path": "data/dashboard/sprint_00-17/predicted_damage.geojson",
        "terms": "Proje çıktısı",
    },
    "change_2022_2023": {
        "name": "Sentinel-2 2022→2023 spektral değişim",
        "role": "Aday değişim alanları; hasar etiketi değil",
        "sprint": "00-18",
        "path": "data/dashboard/sprint_00-18/pre_post_change_map.geojson",
        "terms": "Contains modified Copernicus Sentinel data 2022–2023",
    },
    "osm_2022": {
        "name": "OSM bina kesiti 2022-12-31",
        "role": "Deprem öncesi bina ayak izleri (yerel)",
        "sprint": "00-18",
        "path": "data/external/building_change/buildings_2022.geojson",
        "terms": "ODbL 1.0; © OpenStreetMap katkıcıları",
    },
    "osm_2023": {
        "name": "OSM bina kesiti 2023-02-24",
        "role": "Deprem sonrası bina ayak izleri (yerel)",
        "sprint": "00-19",
        "path": "data/external/reconstruction/osm/buildings_post_event.geojson",
        "terms": "ODbL 1.0; © OpenStreetMap katkıcıları",
    },
    "osm_2026": {
        "name": "OSM bina kesiti 2026-07-27",
        "role": "Güncel bina ayak izleri (yerel)",
        "sprint": "00-19",
        "path": "data/external/reconstruction/osm/buildings_current.geojson",
        "terms": "ODbL 1.0; © OpenStreetMap katkıcıları",
    },
    "reconstruction": {
        "name": "2023–2026 yeniden yapılanma haritası",
        "role": "Kaldırılan/yeni yapı adayları; hasar sınıfı değil",
        "sprint": "00-19",
        "path": "data/dashboard/sprint_00-19/reconstruction_change_map.geojson",
        "terms": "ODbL + Contains modified Copernicus Sentinel data 2023–2026",
    },
    "spatial": {
        "name": "Mekânsal analiz ve sıcak noktalar",
        "role": "Moran's I, LISA, Getis-Ord Gi*",
        "sprint": "00-20",
        "path": "data/dashboard/sprint_00-20/neighborhood_spatial_analysis.geojson",
        "terms": "Proje çıktısı",
    },
}

# Which datasets describe each period on the period selector.
PERIOD_SOURCES = {
    "2022": ("osm_2022", "change_2022_2023"),
    "2023": ("official", "emsr648", "predictions", "osm_2023", "change_2022_2023"),
    "2026": ("osm_2026", "reconstruction"),
}


def source_status(root: Path, key: str) -> dict:
    """Return a registry entry with whether its file exists, its size and modification date."""
    entry = dict(DATA_SOURCES[key], key=key)
    path = Path(root) / entry["path"]
    entry["available"] = path.exists()
    entry["local_only"] = entry["path"].startswith("data/external/")
    if entry["available"]:
        stat = path.stat()
        entry["size_mb"] = round(stat.st_size / 1e6, 2)
        entry["modified"] = datetime.fromtimestamp(stat.st_mtime, UTC).strftime("%Y-%m-%d")
    return entry


def official_class_summary(statistics) -> list[dict]:
    """Totals and shares of the six official classes across all neighbourhoods."""
    totals = {key: int(statistics[key].sum()) for key, _, _ in OFFICIAL_CLASSES}
    grand_total = sum(totals.values())
    return [
        {"key": key, "label": label, "color": color, "count": totals[key],
         "share": totals[key] / grand_total if grand_total else 0.0}
        for key, label, color in OFFICIAL_CLASSES
    ]


def assign_districts(neighborhoods, districts, name_field: str = "shapeName"):
    """Neighbourhood → district by largest overlap area (both inputs in a metric CRS)."""
    import geopandas as gpd

    pieces = gpd.overlay(
        neighborhoods[["neighborhood_id", "mahalle", "geometry"]],
        districts[[name_field, "geometry"]],
        how="intersection",
        keep_geom_type=True,
    )
    pieces["overlap_m2"] = pieces.geometry.area
    totals = pieces.groupby("neighborhood_id")["overlap_m2"].sum()
    best = pieces.sort_values("overlap_m2").groupby("neighborhood_id").tail(1).copy()
    best["district_share"] = (
        best["overlap_m2"].to_numpy() / totals.loc[best["neighborhood_id"]].to_numpy()
    )
    result = best.rename(columns={name_field: "district"})[
        ["neighborhood_id", "mahalle", "district", "district_share"]
    ]
    missing = set(neighborhoods["neighborhood_id"]) - set(result["neighborhood_id"])
    if missing:
        raise ValueError(f"Neighbourhoods outside both districts: {sorted(missing)}")
    return result.sort_values("mahalle").reset_index(drop=True)


def district_class_summary(statistics, districts) -> list[dict]:
    """Official class counts per district, using the neighbourhood → district table."""
    merged = statistics.merge(districts[["neighborhood_id", "district"]], on="neighborhood_id",
                              how="left", validate="one_to_one")
    if merged["district"].isna().any():
        raise ValueError("Some neighbourhoods have no district assignment")
    rows = []
    for district, group in merged.groupby("district"):
        for key, label, color in OFFICIAL_CLASSES:
            rows.append({"district": district, "key": key, "label": label, "color": color,
                         "count": int(group[key].sum())})
    return rows


def prepare(root: Path, config: dict) -> dict:
    """Write the neighbourhood → district table used by the home page."""
    import geopandas as gpd

    root = Path(root)
    metric = config["metric_crs"]
    neighborhoods = gpd.read_file(root / config["neighborhoods"]).to_crs(metric)
    districts = gpd.read_file(root / config["district_boundaries"])
    districts = districts[districts["shapeID"].isin(config["district_shape_ids"])].to_crs(metric)
    if len(districts) != len(config["district_shape_ids"]):
        raise ValueError("Pinned district shape IDs not found in the boundary file")
    table = assign_districts(neighborhoods, districts)
    output = root / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    path = output / "neighborhood_districts.csv"
    table.round({"district_share": 4}).to_csv(path, index=False, encoding="utf-8")
    summary = {
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "neighborhoods": len(table),
        "district_counts": table["district"].value_counts().to_dict(),
        "minimum_district_share": round(float(table["district_share"].min()), 4),
        "source": config["district_boundaries"],
        "method": "largest overlap area in " + metric,
    }
    (output / "neighborhood_districts.source.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return summary
