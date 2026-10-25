
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT / "data" / "processed"
    / "building_features.csv"
)

OUTPUT_DIR = ROOT / "reports" / "sprint_00-10"


def main():
    df = pd.read_csv(INPUT)

    print("=== GEOMETRI KALITE ANALIZI ===")

    print("\nALAN ESİKLERİ:")

    thresholds = [1, 10, 30, 100, 1000, 10000]

    for value in thresholds:
        count = (df["building_area_m2"] < value).sum()

        print(f"Alan < {value} m2: {count}")

    print("\nBUYUK ALANLAR:")

    for value in [5000, 10000, 50000, 100000]:
        count = (df["building_area_m2"] > value).sum()

        print(f"Alan > {value} m2: {count}")

    print("\nSEKIL INDISI:")

    for value in [2, 3, 5, 10]:
        count = (df["shape_index"] > value).sum()

        print(f"Shape index > {value}: {count}")

    print("\nHASAR SINIFINA GORE ALAN:")

    print(
        df.groupby("damage_class")[
            "building_area_m2"
        ].describe().round(2)
    )

    print("\nEN BUYUK 10 GEOMETRI:")

    print(
        df.nlargest(10, "building_area_m2")[
            [
                "building_id",
                "building_area_m2",
                "shape_index",
                "damage_class",
            ]
        ].to_string(index=False)
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df.nlargest(
        100, "building_area_m2"
    ).to_csv(
        OUTPUT_DIR / "largest_geometries.csv",
        index=False
    )

    print("\nRapor kaydedildi.")


if __name__ == "__main__":
    main()
