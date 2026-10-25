
from pathlib import Path

import geopandas as gpd
ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT / "data" / "processed"
    / "aoi_mahalleler.gpkg"
)

OUTPUT = (
    ROOT / "data" / "processed"
    / "v3_neighborhood_features.csv"
)


def main():
    gdf = gpd.read_file(INPUT)

    if gdf.crs is None:
        raise ValueError("CRS bulunamadi")

    metric = gdf.to_crs("EPSG:32637").copy()

    if metric["id"].duplicated().any():
        raise ValueError("Tekrarlanan OSM ID var")

    metric["area_km2"] = (
        metric.geometry.area / 1_000_000
    )

    metric["perimeter_km"] = (
        metric.geometry.length / 1000
    )

    centroids = metric.geometry.centroid

    metric["centroid_x"] = centroids.x
    metric["centroid_y"] = centroids.y

    columns = [
        "id",
        "mahalle",
        "area_km2",
        "perimeter_km",
        "centroid_x",
        "centroid_y",
    ]

    result = metric[columns].copy()

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig"
    )

    print("=== V3 MAHALLE OZNITELIKLERI ===")
    print(f"Poligon sayisi: {len(result)}")

    print("\nALAN ISTATISTIKLERI:")
    print(result["area_km2"].describe())

    print("\nTEKRAR EDEN MAHALLE ADLARI:")
    print(
        result[
            result["mahalle"].duplicated(
                keep=False
            )
        ][["id", "mahalle", "area_km2"]]
        .to_string(index=False)
    )

    print(f"\nKaydedildi: {OUTPUT}")


if __name__ == "__main__":
    main()
