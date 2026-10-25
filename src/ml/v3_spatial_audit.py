
from pathlib import Path
import unicodedata

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

OFFICIAL_FILE = (
    ROOT / "data" / "final"
    / "malatya_damage_analysis_ready.csv"
)

BUILDING_FILE = (
    ROOT / "data" / "interim" / "buildings"
    / "EMSR648_AOI05"
    / "EMSR648_AOI05_builtUpA_analysis.geojson"
)

NEIGHBORHOOD_FILE = (
    ROOT / "data" / "processed"
    / "aoi_mahalleler.gpkg"
)

OUTPUT_DIR = ROOT / "reports" / "sprint_00-10"


def normalize_name(value):
    if pd.isna(value):
        return ""

    value = str(value).strip()

    translation = str.maketrans({
        "ı": "i",
        "İ": "i",
        "ğ": "g",
        "Ğ": "g",
        "ş": "s",
        "Ş": "s",
        "ö": "o",
        "Ö": "o",
        "ü": "u",
        "Ü": "u",
        "ç": "c",
        "Ç": "c",
    })

    value = value.translate(translation).lower()

    value = unicodedata.normalize("NFKD", value)
    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )

    value = " ".join(value.split())

    if value.endswith(" mahallesi"):
        value = value[:-10].strip()

    return value


def main():
    official = pd.read_csv(
        OFFICIAL_FILE,
        low_memory=False
    )

    buildings = gpd.read_file(BUILDING_FILE)
    neighborhoods = gpd.read_file(NEIGHBORHOOD_FILE)

    print("=== V3 MEKANSAL VERI DENETIMI ===")

    print(f"Resmi kayit: {len(official)}")
    print(f"Copernicus poligon: {len(buildings)}")
    print(f"Mahalle poligon: {len(neighborhoods)}")

    print("\nMAHALLE SUTUNLARI:")
    print(neighborhoods.columns.tolist())

    print("\nKOORDINAT SISTEMLERI:")
    print("Copernicus:", buildings.crs)
    print("Mahalleler:", neighborhoods.crs)

    print("\nMAHALLE VERISI ORNEGI:")
    print(
        neighborhoods.drop(
            columns="geometry",
            errors="ignore"
        ).head(5).to_string(index=False)
    )

    # Mahalle adini otomatik tahmin etmek yerine
    # kaynak semasinda acikca dogruluyoruz.
    possible_names = [
        "mahalle",
        "name",
        "NAME",
        "name_tr",
        "name:tr",
    ]

    name_column = next(
        (
            col for col in possible_names
            if col in neighborhoods.columns
        ),
        None
    )

    if name_column is None:
        print("\nMahalle adi sutunu belirlenemedi.")
        print("Once yukaridaki sutunlari kontrol edin.")
        return

    neighborhoods = neighborhoods[
        [name_column, "geometry"]
    ].copy()

    neighborhoods["mahalle_key"] = (
        neighborhoods[name_column]
        .apply(normalize_name)
    )

    official["mahalle_key"] = (
        official["mahalle"]
        .apply(normalize_name)
    )

    metric = buildings.to_crs("EPSG:32637")
    areas = neighborhoods.to_crs(metric.crs)

    # Orijinal poligonlari degistirmiyoruz.
    # Sadece mahalle atamasi icin merkez kullaniyoruz.
    points = metric[
        ["building_id", "geometry"]
    ].copy()

    points.geometry = points.geometry.centroid

    joined = gpd.sjoin(
        points,
        areas[["mahalle_key", "geometry"]],
        how="left",
        predicate="within"
    )

    # Sinirda bulunan veya birden fazla mahalleyle
    # eslesen kayitlari gozden geciriyoruz.
    duplicate_matches = joined[
        "building_id"
    ].duplicated().sum()

    print("\nCOKLU ESLESMELER:")
    print(duplicate_matches)

    print("\nMAHALLE BULUNAMAYAN POLIGONLAR:")
    print(joined["mahalle_key"].isna().sum())

    official_counts = (
        official.groupby("mahalle_key")
        .size()
        .rename("official_count")
    )

    copernicus_counts = (
        joined.dropna(subset=["mahalle_key"])
        .groupby("mahalle_key")
        .size()
        .rename("copernicus_count")
    )

    comparison = pd.concat(
        [official_counts, copernicus_counts],
        axis=1
    ).fillna(0)

    comparison = comparison.astype(int)

    comparison["both_sources"] = (
        (comparison["official_count"] > 0)
        & (comparison["copernicus_count"] > 0)
    )

    print("\nORTAK MAHALLE SAYISI:")
    print(comparison["both_sources"].sum())

    print("\nILK 15 MAHALLE:")
    print(
        comparison.sort_values(
            "copernicus_count",
            ascending=False
        ).head(15).to_string()
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    comparison.to_csv(
        OUTPUT_DIR / "v3_neighborhood_coverage.csv",
        encoding="utf-8-sig"
    )

    print("\nRapor kaydedildi.")


if __name__ == "__main__":
    main()
