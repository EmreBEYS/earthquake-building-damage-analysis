
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT / "data" / "interim" / "buildings"
    / "EMSR648_AOI05"
    / "EMSR648_AOI05_builtUpA_analysis.csv"
)

OUTPUT = ROOT / "reports" / "sprint_00-10"


def main():
    df = pd.read_csv(INPUT, low_memory=False)

    print("=== KAYNAK YANLILIGI DENETIMI ===")
    print(f"Kayit sayisi: {len(df)}")

    fields = [
        "building_use",
        "detection_method",
        "geometry_review_flag",
        "geometry_type",
        "source_dataset_id",
    ]

    for field in fields:
        if field not in df.columns:
            continue

        print(f"\n=== {field} ===")

        table = pd.crosstab(
            df[field],
            df["damage_class"],
            margins=True
        )

        print(table.to_string())

        OUTPUT.mkdir(parents=True, exist_ok=True)

        table.to_csv(
            OUTPUT / f"source_bias_{field}.csv"
        )


if __name__ == "__main__":
    main()
