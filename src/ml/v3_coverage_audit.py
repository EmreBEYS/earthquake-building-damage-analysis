
from pathlib import Path

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

COVERAGE = (
    ROOT / "reports" / "sprint_00-10"
    / "v3_neighborhood_coverage.csv"
)

MAPPING = (
    ROOT / "reports" / "sprint_00-10"
    / "v3_name_mapping.csv"
)

NEIGHBORHOODS = (
    ROOT / "data" / "processed"
    / "aoi_mahalleler.gpkg"
)


def main():
    coverage = pd.read_csv(COVERAGE)
    mapping = pd.read_csv(MAPPING)
    neighborhoods = gpd.read_file(NEIGHBORHOODS)

    print("=== V3 KAPSAM DENETIMI ===")

    print("\nMEVCUT ORTAK MAHALLE:")
    print(coverage["both_sources"].sum())

    candidates = mapping[
        mapping["status"] == "candidate"
    ].copy()

    print("\nADAY ESLESMELER:")
    print(
        candidates[
            ["osm_mahalle", "official_candidate"]
        ].to_string(index=False)
    )

    print("\nMANUEL KONTROL:")
    print(
        mapping[
            mapping["status"] == "manual_review"
        ][["osm_mahalle"]].to_string(index=False)
    )

    print("\nMAHALLE POLIGON TEKRARLARI:")

    duplicates = neighborhoods[
        neighborhoods.duplicated(
            subset=["mahalle"],
            keep=False
        )
    ]

    print(
        duplicates[
            ["id", "mahalle"]
        ].to_string(index=False)
    )

    print("\nPOLIGON SAYISI:")
    print(len(neighborhoods))

    print("\nFARKLI MAHALLE ADI:")
    print(neighborhoods["mahalle"].nunique())


if __name__ == "__main__":
    main()
