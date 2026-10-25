
from pathlib import Path

import geopandas as gpd

ROOT = Path(__file__).resolve().parents[2]

BUILDINGS = (
    ROOT / "data" / "interim" / "buildings"
    / "EMSR648_AOI05"
    / "EMSR648_AOI05_builtUpA_analysis.geojson"
)

NEIGHBORHOODS = (
    ROOT / "data" / "processed"
    / "aoi_mahalleler.gpkg"
)

OUTPUT = (
    ROOT / "data" / "processed"
    / "v3_spatial_features.csv"
)


def main():
    buildings = gpd.read_file(BUILDINGS)
    neighborhoods = gpd.read_file(NEIGHBORHOODS)

    buildings = buildings.to_crs("EPSG:32637")
    neighborhoods = neighborhoods.to_crs("EPSG:32637")

    if buildings["building_id"].duplicated().any():
        raise ValueError("Tekrarlanan building_id var")

    neighborhoods = neighborhoods[
        ["id", "mahalle", "geometry"]
    ].copy()

    neighborhoods["area_km2"] = (
        neighborhoods.geometry.area / 1_000_000
    )

    # Merkez noktalariyla mahalle eslestirme
    points = buildings[
        ["building_id", "geometry"]
    ].copy()

    points.geometry = points.geometry.centroid

    joined = gpd.sjoin(
        points,
        neighborhoods,
        how="left",
        predicate="within"
    )

    # Her poligonun tek bir mahalleyle
    # eslesmesini bekliyoruz.
    if joined["building_id"].duplicated().any():
        raise ValueError("Coklu mahalle eslesmesi var")

    if joined["id"].isna().any():
        raise ValueError("Mahalle disinda poligon var")

    joined = joined.merge(
        buildings[
            ["building_id", "area_m2"]
        ],
        on="building_id",
        how="left",
        validate="one_to_one"
    )

    summary = joined.groupby("id").agg(
        copernicus_count=("building_id", "count"),
        mean_polygon_area_m2=("area_m2", "mean"),
        median_polygon_area_m2=("area_m2", "median")
    ).reset_index()

    result = neighborhoods[
        ["id", "mahalle", "area_km2"]
    ].merge(
        summary,
        on="id",
        how="left",
        validate="one_to_one"
    )

    result["copernicus_count"] = (
        result["copernicus_count"].fillna(0).astype(int)
    )

    result["copernicus_per_km2"] = (
        result["copernicus_count"] / result["area_km2"]
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig"
    )

    print("=== V3 MEKANSAL OZNITELIKLER ===")

    print(f"Mahalle poligonu: {len(result)}")

    print("\nPOLIGON SAYISI:")
    print(result["copernicus_count"].describe())

    print("\nPOLIGON YOGUNLUGU:")
    print(result["copernicus_per_km2"].describe())

    print("\nPOLIGON BULUNMAYAN MAHALLELER:")
    print(
        result[result["copernicus_count"] == 0][
            ["id", "mahalle"]
        ].to_string(index=False)
    )

    print("\nTOPLAM ESLESEN POLIGON:")
    print(result["copernicus_count"].sum())

    print(f"\nKaydedildi: {OUTPUT}")


if __name__ == "__main__":
    main()
