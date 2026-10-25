from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data/processed/official_damage"

FILES = [
    "person_01.csv",
    "person_02.csv",
    "person_03.csv",
]

TARGET = "hasar_durumu"

LEAKAGE_COLUMNS = {
    "itiraz_sonucu",
    "mahkeme_sonucu",
    "hasar_durumu_original",
    "source_pdf",
    "source_page",
    "damage_unknown",
    "damage_conflict",
    "quality_status",
}

IDENTIFIER_COLUMNS = {
    "person",
    "aski_kodu",
    "bina_numarasi",
    "sokak",
    "mahalle_original",
    "possible_duplicate",
    "aski_invalid",
    "mahalle_missing",
}

CANDIDATE_FEATURES = [
    "mahalle",
    "bina_alani",
    "bina_cevresi",
    "kat_sayisi",
    "yapi_yasi",
    "zemin_sinifi",
    "fay_uzakligi",
    "yapi_yogunlugu",
    "pga",
]


def load_data():
    frames = [
        pd.read_csv(DATA_DIR / filename, low_memory=False)
        for filename in FILES
    ]

    return pd.concat(frames, ignore_index=True)


def main():
    df = load_data()

    print("\n=== OZ NITELIK DENETIMI ===")

    print("\nMevcut aday oz nitelikler:")
    available = [
        col for col in CANDIDATE_FEATURES
        if col in df.columns
    ]
    print(available)

    print("\nEksik aday oz nitelikler:")
    missing = [
        col for col in CANDIDATE_FEATURES
        if col not in df.columns
    ]
    print(missing)

    print("\nTum sutunlarda eksik veri:")
    print(df.isna().sum().to_string())

    print("\nHedef siniflar:")
    print(df[TARGET].value_counts())

    print("\nModel disinda tutulacak sutunlar:")
    excluded = (
        LEAKAGE_COLUMNS
        | IDENTIFIER_COLUMNS
        | {TARGET}
    )
    print(sorted(excluded & set(df.columns)))

    print("\nMahalle bazinda kayit sayisi:")
    print(df.groupby("mahalle").size().describe())


if __name__ == "__main__":
    main()