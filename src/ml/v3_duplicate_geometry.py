
from pathlib import Path
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT / "data" / "processed"
    / "aoi_mahalleler.gpkg"
)


def main():
    gdf = gpd.read_file(INPUT)

    metric = gdf.to_crs("EPSG:32637")

    hamidiye = metric[
        metric["mahalle"] == "Hamidiye Mahallesi"
    ].copy()

    print("=== HAMIDIYE GEOMETRI DENETIMI ===")

    print(f"Poligon sayisi: {len(hamidiye)}")

    for _, row in hamidiye.iterrows():
        print("\nID:", row["id"])
        print("Alan (km2):", row.geometry.area / 1_000_000)
        print("Gecerli:", row.geometry.is_valid)
        print("Sinirlar:", row.geometry.bounds)

    if len(hamidiye) == 2:
        first = hamidiye.geometry.iloc[0]
        second = hamidiye.geometry.iloc[1]

        intersection = first.intersection(second)

        intersection_area = intersection.area
        union_area = first.union(second).area

        overlap_ratio = (
            intersection_area / union_area
            if union_area > 0
            else 0
        )

        print("\nKESISIM ALANI (m2):")
        print(intersection_area)

        print("\nIoU:")
        print(overlap_ratio)

        print("\nBIRBIRINE MESAFE (m):")
        print(first.distance(second))

        print("\nAYNI GEOMETRI MI?")
        print(first.equals(second))


if __name__ == "__main__":
    main()
