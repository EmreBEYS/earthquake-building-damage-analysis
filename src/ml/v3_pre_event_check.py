
from pathlib import Path
import geopandas as gpd

ROOT = Path(__file__).resolve().parents[2]

AOI_FILE = (
    ROOT / "data" / "raw" / "copernicus"
    / "EMSR648_AOI05"
    / "EMSR648_AOI05_GRA_PRODUCT_areaOfInterestA_r1_v1.shp"
)

SNAPSHOT_DATE = "2023-02-05"


def main():
    aoi = gpd.read_file(AOI_FILE)

    if aoi.crs is None:
        raise ValueError("AOI koordinat sistemi eksik")

    aoi = aoi.to_crs("EPSG:4326")

    xmin, ymin, xmax, ymax = aoi.total_bounds

    print("=== V3 TARIHSEL OSM HAZIRLIK ===")

    print("Hedef tarih:", SNAPSHOT_DATE)

    print("\nCALISMA ALANI SINIRLARI:")
    print(f"Batı: {xmin:.6f}")
    print(f"Güney: {ymin:.6f}")
    print(f"Doğu: {xmax:.6f}")
    print(f"Kuzey: {ymax:.6f}")

    print("\nBBOX:")
    print(f"{xmin},{ymin},{xmax},{ymax}")

    print("\nAOI alan (km2):")

    metric = aoi.to_crs("EPSG:32637")

    print(metric.geometry.area.sum() / 1_000_000)


if __name__ == "__main__":
    main()
