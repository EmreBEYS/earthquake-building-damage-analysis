
"""
Sprint 00-09 — Resmi Hasar Verisi Dogrulama ve Birlestirme

Girdi:
    data/interim/official_damage/official_damage_records.csv

Ciktilar:
    data/processed/official_damage/
    data/final/
    reports/sprint_00-09/

Kurallar:
- Ham veya ara veriler degistirilmez.
- Tekrar adaylari otomatik silinmez.
- Bilinmeyen mahalle bilgisi uydurulmaz.
- Hasar durumlari standartlastirilir.
"""

from pathlib import Path
import json
import re
import unicodedata

import pandas as pd


BASE = Path(__file__).resolve().parent.parent

INPUT = (
    BASE / "data" / "interim"
    / "official_damage" / "official_damage_records.csv"
)

PROCESSED = BASE / "data" / "processed" / "official_damage"
FINAL = BASE / "data" / "final"
REPORTS = BASE / "reports" / "sprint_00-09"

for directory in (PROCESSED, FINAL, REPORTS):
    directory.mkdir(parents=True, exist_ok=True)


REQUIRED_COLUMNS = [
    "person",
    "mahalle",
    "aski_kodu",
    "sokak",
    "bina_numarasi",
    "hasar_durumu",
    "itiraz_sonucu",
    "afet_adi",
    "afet_siddeti",
    "afet_tarihi",
    "mahkeme_sonucu",
    "source_pdf",
    "source_page",
]

DAMAGE_CLASSES = {
    "HASARSIZ": "Hasarsiz",
    "AZHASARLI": "Az hasarli",
    "ORTAHASARLI": "Orta hasarli",
    "AGIRHASARLI": "Agir hasarli",
    "ACILYIKTIRILACAK": "Acil yiktirilacak",
    "ACILYIKILACAK": "Acil yiktirilacak",
    "YIKIK": "Yikik",
}

EXPECTED_PERSONS = {
    "person_01",
    "person_02",
    "person_03",
}

# Mahalle oldugu bilinmeyen genel dosya isimleri
INVALID_MAHALLE = {
    "",
    "PERSON1",
    "PERSON2",
    "PERSON3",
    "PERSON01",
    "PERSON02",
    "PERSON03",
    "LISTE",
    "HASARLISTESI",
    "HASARTESPIT",
    "RAPOR",
    "SONUC",
    "BELGE",
    "PDF",
}


def clean(value):
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_key(value):
    text = clean(value).upper()
    text = text.replace("İ", "I").replace("ı", "I")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(
        c for c in text
        if not unicodedata.combining(c)
    )
    return re.sub(r"[^A-Z0-9]", "", text)


def normalize_mahalle(value):
    text = clean(value)

    # Bos ya da genel adlardan mahalle uretilmez.
    if normalize_key(text) in INVALID_MAHALLE:
        return ""

    text = text.replace("_", " ")
    text = re.sub(
        r"\b(MAHALLESI|MAHALLESİ|MAH\.?)\b",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return clean(text).upper()


def normalize_damage(value):
    return DAMAGE_CLASSES.get(
        normalize_key(value),
        "Bilinmeyen"
    )


def save_csv(data, path):
    data.to_csv(
        path,
        index=False,
        encoding="utf-8-sig"
    )


def main():
    print("\nSPRINT 00-09 — VERI ENTEGRASYONU")
    print("=" * 55)

    if not INPUT.exists():
        raise FileNotFoundError(
            f"Girdi bulunamadi: {INPUT}\n"
            "Once 08_build_official_dataset.py calistirin."
        )

    df = pd.read_csv(
        INPUT,
        dtype=str,
        keep_default_na=False
    )

    missing_columns = [
        c for c in REQUIRED_COLUMNS
        if c not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Eksik sutunlar: {missing_columns}"
        )

    if df.empty:
        raise ValueError("Girdi veri seti bos.")

    df = df[REQUIRED_COLUMNS].copy()

    for column in REQUIRED_COLUMNS:
        df[column] = df[column].map(clean)

    print("Toplam girdi kaydi:", len(df))

    # ------------------------------------------
    # 1. Person kontrolu
    # ------------------------------------------

    df["person"] = df["person"].str.lower()

    unexpected = sorted(
        set(df["person"]) - EXPECTED_PERSONS
    )

    if unexpected:
        print("UYARI: Beklenmeyen person:", unexpected)

    missing_persons = sorted(
        EXPECTED_PERSONS - set(df["person"])
    )

    if missing_persons:
        print("UYARI: Eksik person:", missing_persons)

    # ------------------------------------------
    # 2. Mahalle temizligi
    # ------------------------------------------

    df["mahalle_original"] = df["mahalle"]

    df["mahalle"] = df["mahalle"].map(
        normalize_mahalle
    )

    df["mahalle_missing"] = df["mahalle"].eq("")

    # Ozellikle sayisal dosya isimleri gercek
    # mahalle adi gibi kabul edilmesin.
    numeric_names = df["mahalle"].str.fullmatch(
        r"\d+", na=False
    )

    df.loc[numeric_names, "mahalle"] = ""
    df["mahalle_missing"] = df["mahalle"].eq("")

    # ------------------------------------------
    # 3. Hasar sinifi kontrolu
    # ------------------------------------------

    df["hasar_durumu_original"] = df["hasar_durumu"]

    df["hasar_durumu"] = df[
        "hasar_durumu"
    ].map(normalize_damage)

    df["damage_unknown"] = (
        df["hasar_durumu"] == "Bilinmeyen"
    )

    # ------------------------------------------
    # 4. ASKI kodu kontrolu
    # ------------------------------------------

    df["aski_kodu"] = df["aski_kodu"].map(
        normalize_key
    )

    df["aski_invalid"] = ~df[
        "aski_kodu"
    ].str.fullmatch(r"[A-Z0-9]{5}")

    # ------------------------------------------
    # 5. Tekrar adaylari
    # ------------------------------------------

    # Ayni mahalle ve aski kodu ile gorunen
    # kayitlar incelemeye alinir.
    # Mahalle bilinmiyorsa eslestirme yapilmaz.
    valid_identity = (
        ~df["mahalle_missing"]
        & ~df["aski_invalid"]
    )

    df["possible_duplicate"] = False

    df.loc[
        valid_identity, "possible_duplicate"
    ] = df.loc[
        valid_identity
    ].duplicated(
        subset=["mahalle", "aski_kodu"],
        keep=False
    )

    # ------------------------------------------
    # 6. Celiskili hasar durumlari
    # ------------------------------------------

    df["damage_conflict"] = False

    valid = df.loc[valid_identity].copy()

    class_count = valid.groupby(
        ["mahalle", "aski_kodu"]
    )["hasar_durumu"].transform("nunique")

    df.loc[
        valid.index, "damage_conflict"
    ] = class_count.gt(1)

    # ------------------------------------------
    # 7. Kalite durumu
    # ------------------------------------------

    df["quality_status"] = "OK"

    invalid = (
        df["mahalle_missing"]
        | df["damage_unknown"]
        | df["aski_invalid"]
    )

    review = (
        df["possible_duplicate"]
        | df["damage_conflict"]
    )

    df.loc[review, "quality_status"] = "REVIEW"
    df.loc[invalid, "quality_status"] = "INVALID"

    # ------------------------------------------
    # 8. Person bazli CSV ciktilari
    # ------------------------------------------

    for person in sorted(df["person"].unique()):
        person_df = df[df["person"] == person]

        save_csv(
            person_df,
            PROCESSED / f"{person}.csv"
        )

        print(
            f"{person}: {len(person_df)} kayit"
        )

    # ------------------------------------------
    # 9. Rapor dosyalari
    # ------------------------------------------

    duplicates = df[
        df["possible_duplicate"]
    ].copy()

    conflicts = df[
        df["damage_conflict"]
    ].copy()

    missing_neighborhood = df[
        df["mahalle_missing"]
    ].copy()

    invalid_records = df[
        df["quality_status"] == "INVALID"
    ].copy()

    review_records = df[
        df["quality_status"] == "REVIEW"
    ].copy()

    # Analiz seti: temel alanlari gecerli.
    # Tekrar adaylari korunur.
    analysis_df = df[
        df["quality_status"] != "INVALID"
    ].copy()

    save_csv(
        df,
        FINAL / "malatya_damage_dataset.csv"
    )

    save_csv(
        analysis_df,
        FINAL / "malatya_damage_analysis_ready.csv"
    )

    save_csv(
        duplicates,
        REPORTS / "duplicate_candidates.csv"
    )

    save_csv(
        conflicts,
        REPORTS / "damage_conflicts.csv"
    )

    save_csv(
        missing_neighborhood,
        REPORTS / "missing_mahalle.csv"
    )

    save_csv(
        invalid_records,
        REPORTS / "invalid_records.csv"
    )

    save_csv(
        review_records,
        REPORTS / "review_records.csv"
    )

    person_summary = df.groupby(
        "person"
    ).agg(
        total=("person", "size"),
        mahalle_missing=("mahalle_missing", "sum"),
        invalid_code=("aski_invalid", "sum"),
        duplicate_candidates=("possible_duplicate", "sum"),
        damage_conflicts=("damage_conflict", "sum"),
    ).reset_index()

    save_csv(
        person_summary,
        REPORTS / "person_summary.csv"
    )

    class_summary = pd.crosstab(
        df["person"],
        df["hasar_durumu"]
    )

    class_summary.to_csv(
        REPORTS / "damage_class_distribution.csv",
        encoding="utf-8-sig"
    )

    summary = {
        "total_records": int(len(df)),
        "analysis_records": int(len(analysis_df)),
        "duplicate_candidate_rows": int(
            len(duplicates)
        ),
        "damage_conflict_rows": int(
            len(conflicts)
        ),
        "missing_mahalle_rows": int(
            len(missing_neighborhood)
        ),
        "invalid_rows": int(
            len(invalid_records)
        ),
        "review_rows": int(
            len(review_records)
        ),
        "person_counts": {
            str(k): int(v)
            for k, v in df[
                "person"
            ].value_counts().items()
        },
        "damage_classes": {
            str(k): int(v)
            for k, v in df[
                "hasar_durumu"
            ].value_counts().items()
        },
    }

    (REPORTS / "summary.json").write_text(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    # ------------------------------------------
    # 10. Terminal raporu
    # ------------------------------------------

    print("\n" + "=" * 55)
    print("SPRINT 00-09 SONUC RAPORU")
    print("=" * 55)

    print("Toplam kayit:", len(df))
    print("Analize aday:", len(analysis_df))
    print("Eksik mahalle:", len(missing_neighborhood))
    print("Tekrar adayi:", len(duplicates))
    print("Hasar celiskisi:", len(conflicts))
    print("Gecersiz kayit:", len(invalid_records))
    print("Inceleme gereken:", len(review_records))

    print("\nHASAR SINIFI DAGILIMI")
    print(
        df["hasar_durumu"].value_counts().to_string()
    )

    print("\nPERSON OZETI")
    print(person_summary.to_string(index=False))

    print("\nTamamlandi.")
    print("Nihai veri:", FINAL)
    print("Kalite raporlari:", REPORTS)

    if invalid_records.empty and review_records.empty:
        print("\nTemel kontroller temiz.")
    else:
        print(
            "\nUYARI: Model egitiminden once "
            "kalite raporlarini inceleyin."
        )


if __name__ == "__main__":
    main()
