
from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt

BASE_DIR = Path(__file__).resolve().parent.parent

RAW_DIR = (
    BASE_DIR / "data" / "raw"
    / "copernicus" / "EMSR648_AOI05"
)

aoi_files = list(
    RAW_DIR.rglob("*areaOfInterestA*.shp")
)

building_files = list(
    RAW_DIR.rglob("*builtUpA*.shp")
)

if len(aoi_files) != 1 or len(building_files) != 1:
    raise RuntimeError("Gerekli katmanlar bulunamadi!")

aoi = gpd.read_file(aoi_files[0])
buildings = gpd.read_file(building_files[0])

print("AOI kayit sayisi:", len(aoi))
print("AOI CRS:", aoi.crs)
print("AOI geometrileri:")
print(aoi.geometry.geom_type.value_counts())

# Geometrileri ayni koordinat sistemine getir
aoi = aoi.to_crs(epsg=32637)
buildings = buildings.to_crs(epsg=32637)

# AOI alanini hesapla
aoi_union = aoi.geometry.union_all()

area_km2 = aoi_union.area / 1_000_000
print("AOI alani (km2):", round(area_km2, 2))

# Bina/bloklarin AOI icindeki durumu
inside = buildings.geometry.intersects(aoi_union)

print("AOI ile kesisen kayit:", inside.sum())
print("AOI disindaki kayit:", (~inside).sum())

# Harita
fig, ax = plt.subplots(figsize=(12, 9))

aoi.plot(
    ax=ax,
    facecolor="none",
    edgecolor="red",
    linewidth=2
)

buildings.plot(
    ax=ax,
    column="damage_gra",
    categorical=True,
    legend=True,
    alpha=0.7
)

ax.set_title("Copernicus AOI05 - Malatya")
ax.set_aspect("equal")

output_dir = BASE_DIR / "reports" / "figures"
output_dir.mkdir(parents=True, exist_ok=True)

plt.savefig(
    output_dir / "aoi05_boundaries.png",
    dpi=200,
    bbox_inches="tight"
)

plt.show()
