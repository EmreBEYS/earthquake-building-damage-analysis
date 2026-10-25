
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = (
    ROOT / "reports" / "sprint_00-10"
    / "v3_neighborhood_coverage_validation.csv"
)

OUTPUT_DIR = ROOT / "reports" / "sprint_00-10"

FEATURES = [
    "osm_building_count",
    "osm_buildings_per_km2",
    "osm_mean_area_m2",
    "osm_median_area_m2",
    "osm_footprint_area_ratio",
]


def main():
    print("=== V3 MAHALLE ANALIZI ===")

    df = pd.read_csv(INPUT_FILE)

    required = FEATURES + [
        "id",
        "mahalle",
        "official_total",
        "severe_count",
        "aoi_coverage_ratio",
    ]

    missing = [
        col for col in required
        if col not in df.columns
    ]

    if missing:
        raise ValueError(f"Eksik sutunlar: {missing}")

    if df["id"].duplicated().any():
        raise ValueError("Tekrarlanan mahalle ID bulundu")

    # Yalnizca yuksek kapsama sahip mahalleler.
    selected = df[
        df["aoi_coverage_ratio"] >= 0.90
    ].copy()

    selected = selected[
        selected["official_total"] > 0
    ].copy()

    selected["severe_ratio"] = (
        selected["severe_count"]
        / selected["official_total"]
    )

    print("\nSECILEN MAHALLE:", len(selected))

    print(
        "Resmi kayit:",
        int(selected["official_total"].sum())
    )

    print(
        "Tarihsel OSM binasi:",
        int(selected["osm_building_count"].sum())
    )

    print(
        "\nOSM kaydi sifir olan mahalle:",
        int(
            (selected["osm_building_count"] == 0).sum()
        )
    )

    print("\nAGIR HASAR ORANI DAGILIMI:")
    print(
        selected["severe_ratio"]
        .describe()
        .round(4)
    )

    print("\nSPEARMAN KORELASYONLARI:")

    rows = []

    for feature in FEATURES:
        subset = selected[
            [feature, "severe_ratio"]
        ].replace(
            [np.inf, -np.inf], np.nan
        ).dropna()

        if (
            len(subset) < 4
            or subset[feature].nunique() < 2
            or subset["severe_ratio"].nunique() < 2
        ):
            rho = np.nan
            pvalue = np.nan
        else:
            result = spearmanr(
                subset[feature],
                subset["severe_ratio"]
            )

            rho = float(result.statistic)
            pvalue = float(result.pvalue)

        rows.append({
            "feature": feature,
            "n": len(subset),
            "spearman_rho": rho,
            "p_value": pvalue,
        })

    correlations = pd.DataFrame(rows)

    print(
        correlations.round(4).to_string(index=False)
    )

    print("\nEN YUKSEK AGIR HASAR ORANLARI:")

    columns = [
        "mahalle",
        "official_total",
        "severe_count",
        "severe_ratio",
        "osm_building_count",
        "osm_buildings_per_km2",
    ]

    print(
        selected.sort_values(
            "severe_ratio", ascending=False
        )[columns].head(10).to_string(index=False)
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    selected.to_csv(
        OUTPUT_DIR / "v3_high_coverage_analysis.csv",
        index=False,
        encoding="utf-8-sig"
    )

    correlations.to_csv(
        OUTPUT_DIR / "v3_correlations.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("\nANALIZ TAMAMLANDI.")


if __name__ == "__main__":
    main()
