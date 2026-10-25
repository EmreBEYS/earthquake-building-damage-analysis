
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os

import geopandas as gpd
import httpx

from dotenv import load_dotenv


# ============================================================
# PROJE AYARLARI
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

load_dotenv(ROOT / ".env")

API_KEY = os.getenv("OHSOME_API_KEY", "").strip()

API_URL = (
    "https://api.heigit.org/ohsome-api"
    "/v2/extraction/features.parquet"
)

SNAPSHOT_DATE = "2023-02-05"

OSM_FILTER = (
    "building=* and building!=no "
    "and geometry:polygon"
)


# ============================================================
# DOSYA YOLLARI
# ============================================================

AOI_FILE = (
    ROOT / "data"
    / "raw"
    / "copernicus"
    / "EMSR648_AOI05"
    / "EMSR648_AOI05_GRA_PRODUCT_areaOfInterestA_r1_v1.shp"
)

OUTPUT_DIR = (
    ROOT / "data"
    / "raw"
    / "osm_historical"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "malatya_buildings_2023-02-05.parquet"
)

METADATA_FILE = (
    OUTPUT_DIR
    / "metadata.json"
)


# ============================================================
# YARDIMCI FONKSIYONLAR
# ============================================================

def validate_api_key():
    if not API_KEY:
        raise ValueError(
            "OHSOME_API_KEY bulunamadi. "
            "Proje kokundeki .env dosyasini kontrol edin."
        )


def load_aoi():
    if not AOI_FILE.exists():
        raise FileNotFoundError(
            f"AOI dosyasi bulunamadi: {AOI_FILE}"
        )

    aoi = gpd.read_file(AOI_FILE)

    if aoi.empty:
        raise ValueError("AOI dosyasi bos")

    if aoi.crs is None:
        raise ValueError("AOI koordinat sistemi tanimsiz")

    aoi = aoi.to_crs("EPSG:4326")

    bbox = [
        float(value)
        for value in aoi.total_bounds
    ]

    return aoi, bbox


def download_historical_data(bbox):
    payload = {
        "aoi": bbox,
        "time": SNAPSHOT_DATE,
        "filter": OSM_FILTER,
        "clip": False,
    }

    headers = {
        "Authorization": API_KEY,
        "Accept": "application/octet-stream",
    }

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    temporary_file = OUTPUT_FILE.with_suffix(".download")

    print("\n=== OHSOME API INDIRME ===")
    print("Tarih:", SNAPSHOT_DATE)
    print("BBOX:", bbox)
    print("Filtre:", OSM_FILTER)

    timeout = httpx.Timeout(
        connect=30.0,
        read=300.0,
        write=60.0,
        pool=30.0,
    )

    try:
        with httpx.Client(timeout=timeout) as client:
            with client.stream(
                "POST",
                API_URL,
                json=payload,
                headers=headers,
            ) as response:

                if response.status_code != 200:
                    error_body = response.read().decode(
                        "utf-8",
                        errors="replace"
                    )

                    raise RuntimeError(
                        f"API hatasi: {response.status_code}\n"
                        f"{error_body[:1500]}"
                    )

                with open(temporary_file, "wb") as file:
                    for chunk in response.iter_bytes():
                        file.write(chunk)

        if temporary_file.stat().st_size == 0:
            raise ValueError(
                "Indirilen dosya bos"
            )

        # Indirme ve okuma dogrulandiktan sonra
        # asil dosya adina tasiyoruz.
        gdf = gpd.read_parquet(temporary_file)

        if gdf.crs is None:
            raise ValueError(
                "Indirilen veride CRS bulunamadi"
            )

        if gdf.geometry.isna().any():
            raise ValueError(
                "Indirilen veride eksik geometri var"
            )

        temporary_file.replace(OUTPUT_FILE)

        return gdf

    except Exception:
        if temporary_file.exists():
            temporary_file.unlink()

        raise


def calculate_sha256(path):
    digest = hashlib.sha256()

    with open(path, "rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def save_metadata(bbox, gdf):
    metadata = {
        "source": "ohsome API v2",
        "api_endpoint": API_URL,
        "snapshot_date": SNAPSHOT_DATE,
        "downloaded_at_utc": datetime.now(
            timezone.utc
        ).isoformat(),
        "filter": OSM_FILTER,
        "bbox": bbox,
        "record_count": len(gdf),
        "crs": str(gdf.crs),
        "sha256": calculate_sha256(OUTPUT_FILE),
        "file": str(OUTPUT_FILE.relative_to(ROOT)),
    }

    with open(
        METADATA_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metadata,
            file,
            indent=2,
            ensure_ascii=False
        )


# ============================================================
# ANA PROGRAM
# ============================================================

def main():
    print("=== V3 TARIHSEL OSM VERI SETI ===")

    validate_api_key()

    aoi, bbox = load_aoi()

    print("\nCALISMA ALANI:")
    print(f"AOI alan sayisi: {len(aoi)}")
    print(f"Koordinat sistemi: {aoi.crs}")

    gdf = download_historical_data(bbox)

    print("\n=== INDIRME SONUCLARI ===")

    print(f"Toplam kayit: {len(gdf)}")
    print(f"CRS: {gdf.crs}")

    print("\nSUTUNLAR:")
    print(gdf.columns.tolist())

    print("\nGEOMETRI TURLERI:")
    print(gdf.geometry.geom_type.value_counts())

    print("\nGECERSIZ GEOMETRI:")
    print((~gdf.geometry.is_valid).sum())

    print("\nILK 5 KAYIT:")
    print(
        gdf.drop(
            columns="geometry",
            errors="ignore"
        ).head().to_string(index=False)
    )

    save_metadata(bbox, gdf)

    print("\nDOSYA KAYDEDILDI:")
    print(OUTPUT_FILE)

    print("\nMETADATA:")
    print(METADATA_FILE)

    print("\nV3 tarihsel OSM indirme tamamlandi.")


if __name__ == "__main__":
    main()
