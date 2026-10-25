
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

MANIFESTS = [
    ROOT / "data" / "inventory.csv",
    ROOT / "data" / "manifests" / "interim_datasets.csv",
    ROOT / "data" / "manifests" / "sentinel2_candidates.csv",
    ROOT / "data" / "manifests" / "EMSR648_AOI05_layers.csv",
]


def main():
    print("=== V3 BAGIMSIZ VERI ENVANTERI ===")

    for path in MANIFESTS:
        print("\n" + "=" * 60)
        print(path.relative_to(ROOT))
        print("=" * 60)

        if not path.exists():
            print("DOSYA BULUNAMADI")
            continue

        df = pd.read_csv(path, low_memory=False)

        print(f"Kayit sayisi: {len(df)}")

        print("\nSUTUNLAR:")
        print(df.columns.tolist())

        print("\nTUM KAYITLAR:")
        print(
            df.to_string(
                index=False,
                max_colwidth=80
            )
        )


if __name__ == "__main__":
    main()
