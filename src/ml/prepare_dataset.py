from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = ROOT / "data" / "processed" / "official_damage"

FILES = [
    "person_01.csv",
    "person_02.csv",
    "person_03.csv",
]

TARGET = "hasar_durumu"

LEAKAGE_COLUMNS = [
    "itiraz_sonucu",
    "mahkeme_sonucu",
    "hasar_durumu_original",
    "source_pdf",
    "source_page",
    "quality_status",
]

def load_dataset():
    frames = []

    for filename in FILES:
        path = DATA_DIR / filename

        if not path.exists():
            raise FileNotFoundError(path)

        df = pd.read_csv(path, low_memory=False)

        print(f"{filename}: {len(df)} kayit")

        frames.append(df)

    dataset = pd.concat(
        frames,
        ignore_index=True
    )

    return dataset


def inspect_dataset(df):
    print("\nTOPLAM KAYIT:", len(df))

    print("\nHASAR DAGILIMI:")
    print(df[TARGET].value_counts(dropna=False))

    print("\nEKSIK DEGERLER:")
    print(
        df.isna().sum()
        .sort_values(ascending=False)
        .head(15)
    )

    print("\nOLASI VERI SIZINTISI ALANLARI:")
    print([
        col for col in LEAKAGE_COLUMNS
        if col in df.columns
    ])

    print("\nMAHALLE SAYISI:")
    print(df["mahalle"].nunique())


def main():
    dataset = load_dataset()
    inspect_dataset(dataset)


if __name__ == "__main__":
    main()