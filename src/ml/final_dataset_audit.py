
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "final"

FILES = [
    "malatya_damage_analysis_ready.csv",
    "malatya_damage_dataset.csv",
]


def inspect_dataset(filename):
    path = DATA_DIR / filename

    if not path.exists():
        print(f"Dosya bulunamadi: {path}")
        return None

    df = pd.read_csv(path, low_memory=False)

    print("\n" + "=" * 60)
    print(f"DOSYA: {filename}")
    print("=" * 60)

    print(f"Satir sayisi: {len(df)}")
    print(f"Sutun sayisi: {len(df.columns)}")

    print("\nSUTUNLAR:")
    for col in df.columns:
        print(f"- {col}: {df[col].dtype}")

    print("\nEKSIK DEGERLER:")
    print(df.isna().sum().to_string())

    print("\nILK 3 KAYIT:")
    print(df.head(3).to_string(index=False))

    print("\nTEKRAR EDEN SATIRLAR:")
    print(df.duplicated().sum())

    for target in ["hasar_durumu", "damage_grade"]:
        if target in df.columns:
            print(f"\n{target} DAGILIMI:")
            print(df[target].value_counts(dropna=False))

    return df


def main():
    datasets = {}

    for filename in FILES:
        datasets[filename] = inspect_dataset(filename)

    first = datasets[FILES[0]]
    second = datasets[FILES[1]]

    if first is not None and second is not None:
        print("\n=== VERI SETI KARSILASTIRMASI ===")

        print("Ayni sutunlar mi?")
        print(first.columns.tolist() == second.columns.tolist())

        if first.columns.tolist() == second.columns.tolist():
            print("Ayni veri icerigi mi?")
            print(first.equals(second))


if __name__ == "__main__":
    main()
