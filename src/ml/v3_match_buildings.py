
from pathlib import Path

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

OSM_FILE = (
    ROOT / "data" / "processed"
    / "v3_historical_buildings.parquet"
)

CEMS_FILE = (
    ROOT / "data" / "interim" / "buildings"
    / "EMSR648_AOI05"
    / "EMSR648_AOI05_builtUpA_analysis.geojson"
)

OUTPUT_DIR = (
    ROOT / "reports" / "sprint_00-10"
)

METRIC_CRS = "EPSG:32637"


def main():
    print("=== V3 BINA ESLESTIRME ===")

    osm = gpd.read_parquet(OSM_FILE)
    cems = gpd.read_file(CEMS_FILE)

    osm = osm.to_crs(METRIC_CRS)
    cems = cems.to_crs(METRIC_CRS)

    osm = osm[
        ["osm_key", "geometry"]
    ].copy()

    cems = cems[
        ["building_id", "damage_class", "geometry"]
    ].copy()

    print("OSM:", len(osm))
    print("Copernicus:", len(cems))

    # Kesisen poligon ciftlerini bul.
    candidates = gpd.sjoin(
        osm,
        cems,
        how="inner",
        predicate="intersects"
    )

    print("\nKesisen aday ciftleri:", len(candidates))

    cems_geom = cems.geometry

    rows = []

    for _, row in candidates.iterrows():
        osm_geometry = row.geometry

        cems_geometry = cems_geom.loc[
            row["index_right"]
        ]

        intersection = osm_geometry.intersection(
            cems_geometry
        ).area

        union = osm_geometry.union(
            cems_geometry
        ).area

        iou = intersection / union if union > 0 else 0

        osm_coverage = (
            intersection / osm_geometry.area
            if osm_geometry.area > 0 else 0
        )

        cems_coverage = (
            intersection / cems_geometry.area
            if cems_geometry.area > 0 else 0
        )

        distance = osm_geometry.centroid.distance(
            cems_geometry.centroid
        )

        rows.append({
            "osm_key": row["osm_key"],
            "building_id": row["building_id"],
            "damage_class": row["damage_class"],
            "iou": iou,
            "osm_coverage": osm_coverage,
            "cems_coverage": cems_coverage,
            "centroid_distance_m": distance,
        })

    result = pd.DataFrame(
        rows,
        columns=[
            "osm_key",
            "building_id",
            "damage_class",
            "iou",
            "osm_coverage",
            "cems_coverage",
            "centroid_distance_m",
        ]
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_csv(
        OUTPUT_DIR / "v3_building_match_candidates.csv",
        index=False
    )

    print("\nIOU DAGILIMI:")
    print(result["iou"].describe())

    print("\nESIKLERE GORE ESLESME:")

    for threshold in [0.1, 0.3, 0.5, 0.7]:
        count = (result["iou"] >= threshold).sum()
        print(f"IoU >= {threshold}: {count}")

    print("\nCOKLU OSM ESLESMELERI:")
    print(result["osm_key"].duplicated().sum())

    print("\nCOKLU COPERNICUS ESLESMELERI:")
    print(result["building_id"].duplicated().sum())

    print("\nRAPOR KAYDEDILDI.")


if __name__ == "__main__":
    main()
