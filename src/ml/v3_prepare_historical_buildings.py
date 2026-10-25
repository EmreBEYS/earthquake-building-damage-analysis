
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd


# ============================================================
# PROJE AYARLARI
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

OSM_FILE = (
    ROOT
    / "data"
    / "raw"
    / "osm_historical"
    / "malatya_buildings_2023-02-05.parquet"
)

AOI_FILE = (
    ROOT
    / "data"
    / "raw"
    / "copernicus"
    / "EMSR648_AOI05"
    / "EMSR648_AOI05_GRA_PRODUCT_areaOfInterestA_r1_v1.shp"
)

OUTPUT = (
    ROOT
    / "data"
    / "processed"
    / "v3_historical_buildings.parquet"
)

METRIC_CRS = "EPSG:32637"


# ============================================================
# OSM ETIKETLERINI OKUMA
# ============================================================

def extract_tags(value):
    if value is None:
        return {}

    if isinstance(value, np.ndarray):
        value = value.tolist()

    if isinstance(value, dict):
        return value

    if isinstance(value, (list, tuple)):
        try:
            return dict(value)
        except (TypeError, ValueError):
            return {}

    return {}


# ============================================================
# VERILERI YUKLEME
# ============================================================

def load_data():
    if not OSM_FILE.exists():
        raise FileNotFoundError(OSM_FILE)

    if not AOI_FILE.exists():
        raise FileNotFoundError(AOI_FILE)

    buildings = gpd.read_parquet(OSM_FILE)
    aoi = gpd.read_file(AOI_FILE)

    if buildings.crs is None:
        raise ValueError("OSM CRS tanimsiz")

    if aoi.crs is None:
        raise ValueError("AOI CRS tanimsiz")

    # FIX: geom / geometry farkini gider.
    active_geometry = buildings.geometry.name

    if active_geometry != "geometry":
        buildings = buildings.rename_geometry("geometry")

    print("Aktif geometri:", buildings.geometry.name)

    buildings = buildings.to_crs(METRIC_CRS)
    aoi = aoi.to_crs(METRIC_CRS)

    return buildings, aoi


# ============================================================
# GEOMETRI DOGRULAMA
# ============================================================

def validate_geometry(gdf):
    if gdf.empty:
        raise ValueError("Veri seti bos")

    if gdf.geometry.isna().any():
        raise ValueError("Eksik geometri bulundu")

    if gdf.geometry.is_empty.any():
        raise ValueError("Bos geometri bulundu")

    if (~gdf.geometry.is_valid).any():
        raise ValueError("Gecersiz geometri bulundu")


# ============================================================
# OZNITELIK URETIMI
# ============================================================

def build_features(buildings, aoi):
    aoi_geometry = aoi.geometry.union_all()

    buildings = buildings[
        buildings.geometry.intersects(aoi_geometry)
    ].copy()

    if buildings.empty:
        raise ValueError("AOI icinde bina bulunamadi")

    buildings["osm_key"] = (
        buildings["osm_type"].astype(str)
        + "/"
        + buildings["osm_id"].astype(str)
    )

    if buildings["osm_key"].duplicated().any():
        raise ValueError("Tekrarlanan OSM kimligi var")

    # Tam poligon geometrisini koruyoruz.
    buildings["building_area_m2"] = (
        buildings.geometry.area
    )

    buildings["building_perimeter_m"] = (
        buildings.geometry.length
    )

    area = buildings["building_area_m2"]
    perimeter = buildings["building_perimeter_m"]

    buildings["shape_index"] = np.where(
        area > 0,
        perimeter / (2 * np.sqrt(np.pi * area)),
        np.nan
    )

    buildings["compactness"] = np.where(
        perimeter > 0,
        (4 * np.pi * area) / (perimeter ** 2),
        np.nan
    )

    buildings["aoi_overlap_ratio"] = [
        (
            geom.intersection(aoi_geometry).area
            / geom.area
            if geom.area > 0 else np.nan
        )
        for geom in buildings.geometry
    ]

    # OSM etiketlerini oku.
    tags = buildings["tags"].apply(extract_tags)

    buildings["building_type"] = tags.apply(
        lambda item: item.get("building")
    )

    buildings["building_levels"] = tags.apply(
        lambda item: item.get("building:levels")
    )

    buildings["building_year"] = tags.apply(
        lambda item: item.get("start_date")
    )

    buildings["building_levels"] = pd.to_numeric(
        buildings["building_levels"],
        errors="coerce"
    )

    # Veriyi 5 Subat 2023 kaynagindan aldik.
    # Kaynak zamanini kayit altinda tutuyoruz.
    buildings["snapshot_date"] = "2023-02-05"

    columns = [
        "osm_key",
        "snapshot_date",
        "building_type",
        "building_levels",
        "building_year",
        "building_area_m2",
        "building_perimeter_m",
        "shape_index",
        "compactness",
        "aoi_overlap_ratio",
        "geometry",
    ]

    missing_columns = [
        column
        for column in columns
        if column not in buildings.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Eksik sutunlar: {missing_columns}"
        )

    result = buildings[columns].copy()

    return result


# ============================================================
# KALITE RAPORU
# ============================================================

def print_report(result):
    print("\n=== V3 TARIHSEL BINA HAZIRLIGI ===")

    print(f"AOI ile kesisen bina: {len(result)}")

    print("\nGEOMETRI TURLERI:")
    print(result.geometry.geom_type.value_counts())

    print("\nALAN ISTATISTIKLERI:")
    print(
        result["building_area_m2"]
        .describe()
        .round(2)
    )

    print("\nBINA TURU:")
    print(
        result["building_type"]
        .value_counts(dropna=False)
        .head(15)
    )

    levels_count = (
        result["building_levels"].notna().sum()
    )

    years_count = (
        result["building_year"].notna().sum()
    )

    print("\nKAT SAYISI BULUNAN:")
    print(levels_count)

    print("\nYAPI TARIHI BULUNAN:")
    print(years_count)

    print("\nAOI ORTUSME ORANI:")
    print(
        result["aoi_overlap_ratio"]
        .describe()
        .round(4)
    )

    print("\nEKSIK DEGERLER:")
    print(
        result.isna()
        .sum()
        .to_string()
    )

    print("\nGECERSIZ GEOMETRI:")
    print((~result.geometry.is_valid).sum())

    print("\nBOS GEOMETRI:")
    print(result.geometry.is_empty.sum())


# ============================================================
# ANA PROGRAM
# ============================================================

def main():
    print("=== V3 PRE-EVENT BUILDING FEATURES ===")

    buildings, aoi = load_data()

    print(f"\nHam OSM kaydi: {len(buildings)}")

    validate_geometry(buildings)
    validate_geometry(aoi)

    result = build_features(buildings, aoi)

    # Geometri kontrolu
    validate_geometry(result)

    if result["building_area_m2"].le(0).any():
        raise ValueError(
            "Sifir veya negatif alan bulundu"
        )

    if not np.isfinite(
        result[
            [
                "building_area_m2",
                "building_perimeter_m",
                "shape_index",
                "compactness",
                "aoi_overlap_ratio",
            ]
        ].to_numpy(dtype=float)
    ).all():
        raise ValueError(
            "Gecersiz sayisal oznitelik bulundu"
        )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_parquet(
        OUTPUT,
        index=False
    )

    print_report(result)

    print("\nKAYDEDILDI:")
    print(OUTPUT)

    print("\nV3 tarihsel bina veri seti hazir.")


if __name__ == "__main__":
    main()
