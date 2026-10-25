
from pathlib import Path
import re
import unicodedata

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]

OFFICIAL_DIR = ROOT / "data/processed/official_damage"

FEATURES_FILE = (
    ROOT / "data/processed"
    / "v3_osm_neighborhood_features.csv"
)

OUTPUT_DIR = ROOT / "reports/sprint_00-10"

DAMAGE_CLASSES = [
    "Hasarsiz",
    "Az hasarli",
    "Orta hasarli",
    "Agir hasarli",
    "Acil yiktirilacak",
    "Yikik",
]


def normalize_name(value):
    if pd.isna(value):
        return ""

    name = str(value).strip()

    # Turkce karakterleri standartlastir.
    name = name.replace("ı", "i").replace("İ", "I")
    name = name.upper()

    name = unicodedata.normalize("NFKD", name)
    name = "".join(
        char for char in name
        if not unicodedata.combining(char)
    )

    name = re.sub(r"[^A-Z0-9]", "", name)

    if name.endswith("MAHALLESI"):
        name = name[:-9]

    return name


def main():
    print("=== V3 RESMI HASAR - MAHALLE ESLESTIRME ===")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    files = [
        OFFICIAL_DIR / f"person_{i:02d}.csv"
        for i in range(1, 4)
    ]

    for file in files:
        if not file.exists():
            raise FileNotFoundError(file)

    official = pd.concat(
        [pd.read_csv(file) for file in files],
        ignore_index=True
    )

    features = pd.read_csv(FEATURES_FILE)

    official["name_key"] = (
        official["mahalle"].apply(normalize_name)
    )

    features["name_key"] = (
        features["mahalle"].apply(normalize_name)
    )

    print("Resmi kayit:", len(official))
    print("Mahalle geometrisi:", len(features))

    # Bos veya tekrarlanan isimlere otomatik
    # geometri eslestirmesi yapma.
    geometry_name_counts = (
        features.groupby("name_key")["id"]
        .nunique()
    )

    safe_names = set(
        geometry_name_counts[
            geometry_name_counts == 1
        ].index
    )

    safe_names.discard("")

    official_names = set(
        official["name_key"].unique()
    )

    common_names = safe_names & official_names

    print("\nKesin ve tekil eslesen ad:")
    print(len(common_names))

    matched_official = official[
        official["name_key"].isin(common_names)
    ].copy()

    matched_features = features[
        features["name_key"].isin(common_names)
    ].copy()

    print("Eslesen resmi kayit:")
    print(len(matched_official))

    print("Eslesmeyen resmi kayit:")
    print(len(official) - len(matched_official))

    # Hasar sinifi degerlerini dogrula.
    unknown_classes = set(
        matched_official["hasar_durumu"].dropna()
    ) - set(DAMAGE_CLASSES)

    if unknown_classes:
        raise ValueError(
            f"Bilinmeyen hasar siniflari: {unknown_classes}"
        )

    counts = pd.crosstab(
        matched_official["name_key"],
        matched_official["hasar_durumu"]
    )

    counts = counts.reindex(
        columns=DAMAGE_CLASSES,
        fill_value=0
    )

    counts = counts.reset_index()

    result = matched_features.merge(
        counts,
        on="name_key",
        how="left",
        validate="one_to_one"
    )

    result["official_total"] = (
        result[DAMAGE_CLASSES].sum(axis=1)
    )

    severe = [
        "Agir hasarli",
        "Acil yiktirilacak",
        "Yikik"
    ]

    result["severe_count"] = (
        result[severe].sum(axis=1)
    )

    result["severe_ratio"] = (
        result["severe_count"]
        / result["official_total"]
    )

    # Bu oran yalnizca kayitli resmi
    # hasar degerlendirmeleri icindeki orandir.
    # Mahalledeki tum binalarin hasar orani
    # olarak yorumlanmamalidir.

    result.to_csv(
        OUTPUT_DIR / "v3_official_osm_exact_match.csv",
        index=False,
        encoding="utf-8-sig"
    )

    unmatched_official = official[
        ~official["name_key"].isin(common_names)
    ][["mahalle", "name_key"]].drop_duplicates()

    unmatched_features = features[
        ~features["name_key"].isin(common_names)
    ][["id", "mahalle", "name_key"]].copy()

    unmatched_official.to_csv(
        OUTPUT_DIR / "v3_unmatched_official_names.csv",
        index=False,
        encoding="utf-8-sig"
    )

    unmatched_features.to_csv(
        OUTPUT_DIR / "v3_unmatched_osm_names.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("\nBIRLESTIRME SONUCU:")
    print("Eslesen mahalle satiri:", len(result))
    print("Resmi toplam:", result["official_total"].sum())

    print("\nESLESMEYEN RESMI MAHALLELER:")
    print(
        unmatched_official.to_string(index=False)
    )

    print("\nESLESMEYEN OSM MAHALLELERI:")
    print(
        unmatched_features.to_string(index=False)
    )

    print("\nKAYDEDILDI:")
    print(
        OUTPUT_DIR / "v3_official_osm_exact_match.csv"
    )


if __name__ == "__main__":
    main()
