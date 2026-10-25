
from pathlib import Path
from difflib import get_close_matches
import unicodedata

import geopandas as gpd
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

OFFICIAL = (
    ROOT / "data" / "final"
    / "malatya_damage_analysis_ready.csv"
)

NEIGHBORHOODS = (
    ROOT / "data" / "processed"
    / "aoi_mahalleler.gpkg"
)

OUTPUT = (
    ROOT / "reports" / "sprint_00-10"
    / "v3_name_review.csv"
)


def normalize(value):
    value = str(value).strip().lower()

    value = value.translate(str.maketrans({
        "ı": "i",
        "ğ": "g",
        "ş": "s",
        "ö": "o",
        "ü": "u",
        "ç": "c",
    }))

    value = unicodedata.normalize("NFKD", value)

    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )

    value = " ".join(value.split())

    if value.endswith(" mahallesi"):
        value = value.removesuffix(" mahallesi").strip()

    return value


def main():
    official = pd.read_csv(OFFICIAL, low_memory=False)
    neighborhoods = gpd.read_file(NEIGHBORHOODS)

    official_names = {
        normalize(name): name
        for name in official["mahalle"].unique()
    }

    osm_names = {
        normalize(name): name
        for name in neighborhoods["mahalle"].dropna().unique()
    }

    rows = []

    for key, original_name in osm_names.items():
        if key in official_names:
            continue

        suggestions = get_close_matches(
            key,
            official_names.keys(),
            n=3,
            cutoff=0.55
        )

        rows.append({
            "osm_mahalle": original_name,
            "normalized": key,
            "suggestions": " | ".join(
                official_names[s] for s in suggestions
            ),
            "review_status": "manual_review"
        })

    result = pd.DataFrame(
        rows,
        columns=[
            "osm_mahalle",
            "normalized",
            "suggestions",
            "review_status"
        ]
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig"
    )

    print("=== MAHALLE ADI DENETIMI ===")
    print(f"Resmi mahalle: {len(official_names)}")
    print(f"OSM mahalle: {len(osm_names)}")
    print(f"Incelenecek isim: {len(result)}")

    print("\nINCELEME LISTESI:")
    print(result.to_string(index=False))

    print(f"\nRapor: {OUTPUT}")


if __name__ == "__main__":
    main()
