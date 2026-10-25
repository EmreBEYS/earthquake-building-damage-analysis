
from pathlib import Path
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[2]

BUILDING_FILE = (
    ROOT
    / "data"
    / "interim"
    / "buildings"
    / "EMSR648_AOI05"
    / "EMSR648_AOI05_builtUpA_analysis.geojson"
)


def main():
    if not BUILDING_FILE.exists():
        raise FileNotFoundError(BUILDING_FILE)

    gdf = gpd.read_file(BUILDING_FILE)

    print("\n=== COPERNICUS BINA VERISI ===")

    print(f"Kayit sayisi: {len(gdf)}")
    print(f"Koordinat sistemi: {gdf.crs}")

    print("\nSUTUNLAR:")
    for column in gdf.columns:
        print(f"- {column}: {gdf[column].dtype}")

    print("\nGEOMETRI TURleri:")
    print(gdf.geometry.geom_type.value_counts())

    print("\nEKSIK DEGERLER:")
    print(gdf.isna().sum().to_string())

    print("\nILK 3 KAYIT:")
    attributes = gdf.drop(
        columns="geometry",
        errors="ignore"
    )
    print(attributes.head(3).to_string(index=False))

    print("\nCOGRAFI SINIRLAR:")
    print(gdf.total_bounds)

    print("\nGECERSIZ GEOMETRILER:")
    print((~gdf.geometry.is_valid).sum())

    print("\nBOS GEOMETRILER:")
    print(gdf.geometry.is_empty.sum())


if __name__ == "__main__":
    main()
