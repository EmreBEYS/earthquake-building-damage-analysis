
from pathlib import Path

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

NEIGHBORHOODS_FILE = (
    ROOT / "data/processed/aoi_mahalleler.gpkg"
)

AOI_FILE = (
    ROOT / "data/raw/copernicus/EMSR648_AOI05"
    / "EMSR648_AOI05_GRA_PRODUCT_areaOfInterestA_r1_v1.shp"
)

MATCHED_FILE = (
    ROOT / "reports/sprint_00-10"
    / "v3_official_osm_exact_match.csv"
)

OUTPUT_DIR = ROOT / "reports/sprint_00-10"

METRIC_CRS = "EPSG:32637"


def main():
    print("=== V3 MAHALLE KAPSAM DOGRULAMA ===")

    neighborhoods = gpd.read_file(
        NEIGHBORHOODS_FILE
    ).to_crs(METRIC_CRS)

    aoi = gpd.read_file(
        AOI_FILE
    ).to_crs(METRIC_CRS)

    matched = pd.read_csv(MATCHED_FILE)

    if not neighborhoods["id"].is_unique:
        raise ValueError(
            "Mahalle geometri ID degerleri tekil degil"
        )

    if not matched["id"].is_unique:
        raise ValueError(
            "Eslesen mahalle ID degerleri tekil degil"
        )

    aoi_geometry = aoi.geometry.union_all()

    neighborhoods["full_area_m2"] = (
        neighborhoods.geometry.area
    )

    neighborhoods["aoi_area_m2"] = (
        neighborhoods.geometry.apply(
            lambda geom: geom.intersection(
                aoi_geometry
            ).area
        )
    )

    neighborhoods["aoi_coverage_ratio"] = (
        neighborhoods["aoi_area_m2"]
        / neighborhoods["full_area_m2"]
    )

    coverage = neighborhoods[
        [
            "id",
            "full_area_m2",
            "aoi_area_m2",
            "aoi_coverage_ratio"
        ]
    ].copy()

    result = matched.merge(
        coverage,
        on="id",
        how="left",
        validate="one_to_one"
    )

    if result["aoi_coverage_ratio"].isna().any():
        raise ValueError(
            "Bazi mahalle geometrileri bulunamadi"
        )

    # Bu esikler model karari degil,
    # inceleme amacli kapsama kategorileridir.
    def classify_coverage(ratio):
        if ratio >= 0.90:
            return "high"
        if ratio >= 0.50:
            return "medium"
        return "low"

    result["coverage_group"] = (
        result["aoi_coverage_ratio"]
        .apply(classify_coverage)
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    output_file = (
        OUTPUT_DIR
        / "v3_neighborhood_coverage_validation.csv"
    )

    result.to_csv(
        output_file,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nTOPLAM ESLESEN MAHALLE:")
    print(len(result))

    print("\nKAPSAM GRUPLARI:")
    print(
        result["coverage_group"].value_counts()
    )

    print("\nKAPSAM ORANI DAGILIMI:")
    print(
        result["aoi_coverage_ratio"]
        .describe()
        .round(4)
    )

    print("\nYUKSEK KAPSAMLI MAHALLELER:")
    high = result[
        result["coverage_group"] == "high"
    ]

    print("Mahalle:", len(high))
    print(
        "Resmi hasar kaydi:",
        high["official_total"].sum()
    )
    print(
        "OSM binasi:",
        high["osm_building_count"].sum()
    )

    print("\nDUSUK KAPSAMLI MAHALLELER:")
    low = result[
        result["coverage_group"] == "low"
    ].sort_values(
        "aoi_coverage_ratio"
    )

    print(
        low[
            [
                "mahalle",
                "aoi_coverage_ratio",
                "official_total",
                "osm_building_count"
            ]
        ].to_string(index=False)
    )

    print("\nKAYDEDILDI:")
    print(output_file)


if __name__ == "__main__":
    main()
