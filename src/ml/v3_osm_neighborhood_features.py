
from pathlib import Path

import geopandas as gpd
ROOT = Path(__file__).resolve().parents[2]

OSM_FILE = (
    ROOT / "data/processed"
    / "v3_historical_buildings.parquet"
)

NEIGHBORHOOD_FILE = (
    ROOT / "data/processed"
    / "aoi_mahalleler.gpkg"
)

OUTPUT_FILE = (
    ROOT / "data/processed"
    / "v3_osm_neighborhood_features.csv"
)

METRIC_CRS = "EPSG:32637"


def main():
    print("=== V3 DEPREM ONCESI MAHALLE OZELLIKLERI ===")

    osm = gpd.read_parquet(OSM_FILE)
    neighborhoods = gpd.read_file(NEIGHBORHOOD_FILE)

    osm = osm.to_crs(METRIC_CRS)
    neighborhoods = neighborhoods.to_crs(METRIC_CRS)

    if not {"id", "mahalle"}.issubset(
        neighborhoods.columns
    ):
        raise ValueError(
            "Mahalle dosyasinda id veya mahalle eksik"
        )

    if neighborhoods["id"].duplicated().any():
        raise ValueError("Mahalle geometrisi ID tekrari")

    neighborhoods = neighborhoods[
        ["id", "mahalle", "geometry"]
    ].copy()

    neighborhoods["mahalle_area_km2"] = (
        neighborhoods.geometry.area / 1_000_000
    )

    # Her OSM binasini merkez noktasiyla
    # bir mahalleye atamaya calisiyoruz.
    osm_points = osm[
        ["osm_key", "building_area_m2", "geometry"]
    ].copy()

    osm_points["geometry"] = (
        osm_points.geometry.centroid
    )

    joined = gpd.sjoin(
        osm_points,
        neighborhoods[["id", "geometry"]],
        how="left",
        predicate="within"
    )

    # Bir bina birden fazla mahalleye
    # atanirsa otomatik karar vermiyoruz.
    matched = joined.dropna(subset=["id"]).copy()

    match_counts = (
        matched.groupby("osm_key").size()
    )

    ambiguous_ids = match_counts[
        match_counts > 1
    ].index

    accepted = matched[
        ~matched["osm_key"].isin(ambiguous_ids)
    ].copy()

    unique_matched = accepted[
        "osm_key"
    ].nunique()

    unmatched_count = (
        len(osm)
        - match_counts.index.nunique()
    )

    print("\nHAM VERI:")
    print("OSM binasi:", len(osm))
    print("Mahalle poligonu:", len(neighborhoods))

    print("\nATAMA KONTROLU:")
    print("Tek mahalleye atanan:", unique_matched)
    print("Eslesmeyen bina:", unmatched_count)
    print(
        "Birden fazla mahalleye atanan:",
        len(ambiguous_ids)
    )

    summary = accepted.groupby("id").agg(
        osm_building_count=(
            "osm_key", "nunique"
        ),
        osm_mean_area_m2=(
            "building_area_m2", "mean"
        ),
        osm_median_area_m2=(
            "building_area_m2", "median"
        ),
        osm_total_area_m2=(
            "building_area_m2", "sum"
        ),
    ).reset_index()

    result = neighborhoods[
        ["id", "mahalle", "mahalle_area_km2"]
    ].merge(
        summary,
        on="id",
        how="left",
        validate="one_to_one"
    )

    result["osm_building_count"] = (
        result["osm_building_count"]
        .fillna(0)
        .astype(int)
    )

    result["osm_total_area_m2"] = (
        result["osm_total_area_m2"]
        .fillna(0)
    )

    result["osm_buildings_per_km2"] = (
        result["osm_building_count"]
        / result["mahalle_area_km2"]
    )

    result["osm_footprint_area_ratio"] = (
        result["osm_total_area_m2"]
        / (result["mahalle_area_km2"] * 1_000_000)
    )

    OUTPUT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_csv(
        OUTPUT_FILE,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nSONUC:")
    print("Mahalle satiri:", len(result))
    print(
        "Toplam atanan bina:",
        result["osm_building_count"].sum()
    )

    print(
        "OSM kaydi bulunmayan mahalle:",
        (result["osm_building_count"] == 0).sum()
    )

    print("\nBINA YOGUNLUGU:")
    print(
        result["osm_buildings_per_km2"]
        .describe()
        .round(2)
    )

    print("\nILK 10 MAHALLE:")
    print(
        result.sort_values(
            "osm_building_count",
            ascending=False
        )[
            [
                "mahalle",
                "osm_building_count",
                "osm_buildings_per_km2",
                "osm_median_area_m2",
            ]
        ].head(10).to_string(index=False)
    )

    print("\nKAYDEDILDI:")
    print(OUTPUT_FILE)


if __name__ == "__main__":
    main()
