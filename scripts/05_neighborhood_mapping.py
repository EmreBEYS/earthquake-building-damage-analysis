
from pathlib import Path
import geopandas as gpd
import pandas as pd

BASE = Path(__file__).resolve().parent.parent

COPERNICUS = (
    BASE / "data/raw/copernicus/EMSR648_AOI05"
)
OSM = BASE / "data/raw/osm/malatya_mahalleler.geojson"
OUTPUT = BASE / "data/processed"

OUTPUT.mkdir(parents=True, exist_ok=True)

# 1. Copernicus verilerini oku
aoi_file = next(COPERNICUS.rglob("*areaOfInterestA*.shp"))
building_file = next(COPERNICUS.rglob("*builtUpA*.shp"))

aoi = gpd.read_file(aoi_file)
buildings = gpd.read_file(building_file)
neighborhoods = gpd.read_file(OSM)

# 2. Koordinat sistemlerini esitle
aoi = aoi.to_crs(epsg=32637)
buildings = buildings.to_crs(epsg=32637)
neighborhoods = neighborhoods.to_crs(epsg=32637)

# 3. Mahalle isimlerini kontrol et
print("Mahalle sutunlari:", neighborhoods.columns.tolist())

if "name" not in neighborhoods.columns:
    raise ValueError("Mahalle adi sutunu bulunamadi.")

neighborhoods = neighborhoods[
    neighborhoods.geometry.geom_type.isin(
        ["Polygon", "MultiPolygon"]
    )
].copy()

neighborhoods["mahalle"] = neighborhoods["name"]

# 4. AOI ile kesisen mahalleleri bul
aoi_geometry = aoi.geometry.union_all()

mask = neighborhoods.intersects(aoi_geometry)
selected = neighborhoods.loc[mask].copy()

print("AOI ile kesisen mahalle sayisi:", len(selected))

# 5. Bina/blok merkeziyle mahalle eslestir
# Orijinal geometriyi koruyoruz.
centers = buildings.copy()
centers["geometry"] = buildings.geometry.representative_point()

joined = gpd.sjoin(
    centers,
    selected[["mahalle", "geometry"]],
    how="left",
    predicate="within"
)

# Birden fazla mahalleyle eslesen kayitlari kontrol et
ambiguous = joined.index[joined.index.duplicated()].unique()

print("Coklu eslesen kayit:", len(ambiguous))
print(
    "Mahallesi bulunamayan kayit:",
    joined["mahalle"].isna().sum()
)

# 6. Mahalle bazinda hasar dagilimi
summary = pd.crosstab(
    joined["mahalle"].fillna("ESLESMEYEN"),
    joined["damage_gra"]
)

summary["toplam_kayit"] = summary.sum(axis=1)

summary = summary.sort_values(
    "toplam_kayit",
    ascending=False
)

# 7. Dosyalari kaydet
summary.to_csv(
    OUTPUT / "mahalle_hasar_ozeti.csv",
    encoding="utf-8-sig"
)

selected.to_file(
    OUTPUT / "aoi_mahalleler.gpkg",
    driver="GPKG"
)

print("\nMAHALLE BAZLI HASAR OZETI")
print(summary.to_string())

print("\nCSV ve GPKG dosyalari olusturuldu.")
