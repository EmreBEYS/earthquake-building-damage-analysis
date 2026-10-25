
from pathlib import Path
import numpy as np
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT / "data" / "interim" / "buildings"
    / "EMSR648_AOI05"
    / "EMSR648_AOI05_builtUpA_analysis.geojson"
)

OUTPUT = ROOT / "data" / "processed" / "building_features.csv"


def main():
    gdf = gpd.read_file(INPUT)

    if gdf.crs is None:
        raise ValueError("Koordinat sistemi tanimsiz")

    if gdf.geometry.isna().any():
        raise ValueError("Eksik geometri var")

    if (~gdf.geometry.is_valid).any():
        raise ValueError("Gecersiz geometri var")

    # Malatya icin metre tabanli UTM 37N
    metric = gdf.to_crs("EPSG:32637")

    metric["building_area_m2"] = metric.geometry.area
    metric["building_perimeter_m"] = metric.geometry.length

    area = metric["building_area_m2"]
    perimeter = metric["building_perimeter_m"]

    # 4*pi*A / P^2
    metric["compactness"] = np.where(
        perimeter > 0,
        4 * np.pi * area / (perimeter ** 2),
        np.nan
    )

    metric["shape_index"] = np.where(
        area > 0,
        perimeter / (2 * np.sqrt(np.pi * area)),
        np.nan
    )

    columns = [
        "building_id",
        "building_area_m2",
        "building_perimeter_m",
        "compactness",
        "shape_index",
        "damage_class",
    ]

    result = metric[columns].copy()

    if result["building_id"].duplicated().any():
        raise ValueError("Tekrarlanan building_id var")

    if result.isna().any().any():
        raise ValueError("Eksik oznitelik var")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT, index=False)

    print("=== FEATURE ENGINEERING ===")
    print(f"Bina sayisi: {len(result)}")
    print("\nHasar siniflari:")
    print(result["damage_class"].value_counts())

    print("\nOznitelik istatistikleri:")
    print(
        result[
            [
                "building_area_m2",
                "building_perimeter_m",
                "compactness",
                "shape_index",
            ]
        ].describe()
    )

    print(f"\nKaydedildi: {OUTPUT}")


if __name__ == "__main__":
    main()
