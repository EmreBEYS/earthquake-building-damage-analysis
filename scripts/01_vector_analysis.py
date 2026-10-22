
from pathlib import Path
import geopandas as gpd

# Projenin ana klasoru
BASE_DIR = Path(__file__).resolve().parent.parent

# Copernicus bina hasar katmani
vector_dir = BASE_DIR / "data" / "raw" / "copernicus" / "EMSR648_AOI05"

# SHP dosyasini bul
files = list(vector_dir.rglob("*builtUpA*.shp"))

print("Bulunan bina katmani:", len(files))

for file in files:
    print("\nDosya:", file.name)

    gdf = gpd.read_file(file)

    print("Bina/alan kayit sayisi:", len(gdf))
    print("Koordinat sistemi:", gdf.crs)
    print("Sutunlar:", gdf.columns.tolist())

    print("\nIlk 5 kayit:")
    print(gdf.drop(columns="geometry").head())

    print("\nGeometri turleri:")
    print(gdf.geometry.geom_type.value_counts())

    print("\nEksik geometriler:")
    print(gdf.geometry.isna().sum())

    print("\nGecersiz geometriler:")
    print((~gdf.geometry.is_valid).sum())
    # Hasar siniflarinin dagilimi
    print("\nHASAR SINIFI DAGILIMI")
    print("-" * 40)

    damage_counts = gdf["damage_gra"].value_counts(
    dropna=False
    )

    print(damage_counts)

    # Hasar siniflarinin yuzdelik oranlari
    print("\nHASAR SINIFI YUZDELERI")

    damage_percent = gdf["damage_gra"].value_counts(
    normalize=True,
    dropna=False
    ) * 100

    print(damage_percent.round(2))

    # Nesne turleri ve notasyon bilgisi
    print("\nNESNE TURLERI")
    print(gdf["obj_type"].value_counts(dropna=False))

    print("\nNOTASYON")
    print(gdf["notation"].value_counts(dropna=False))

    # Ayni geometriye sahip tekrarli kayitlar
    print("\nTEKRARLI GEOMETRI SAYISI")
    print(gdf.geometry.to_wkb().duplicated().sum())

# Copernicus verisindeki yer adlarini incele
print("\nCOPERNICUS YER ADLARI")
print("-" * 45)

print(
    gdf["name"].value_counts(
        dropna=False
    ).to_string()
)

# Kapsanan koordinat araligi
print("\nCOPERNICUS KOORDINAT SINIRLARI")

minx, miny, maxx, maxy = gdf.total_bounds

print("Bati:", minx)
print("Guney:", miny)
print("Dogu:", maxx)
print("Kuzey:", maxy)

print("\nCOPERNICUS YER ADLARI")
print(gdf["name"].value_counts().to_string())



