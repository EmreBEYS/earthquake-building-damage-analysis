
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT / "reports/sprint_00-10"
    / "v3_high_coverage_analysis.csv"
)

OUTPUT = (
    ROOT / "reports/sprint_00-10"
    / "v3_robustness_results.csv"
)

FEATURES = [
    "osm_building_count",
    "osm_buildings_per_km2",
    "osm_mean_area_m2",
    "osm_median_area_m2",
    "osm_footprint_area_ratio",
]


def calculate_correlations(df, scenario):
    rows = []

    for feature in FEATURES:
        subset = df[
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
            "scenario": scenario,
            "feature": feature,
            "n": len(subset),
            "spearman_rho": rho,
            "p_value": pvalue,
        })

    return rows


def main():
    print("=== V3 DUYARLILIK ANALIZI ===")

    df = pd.read_csv(INPUT)

    scenarios = {
        "all_high_coverage": df,
        "osm_at_least_1": df[
            df["osm_building_count"] >= 1
        ],
        "osm_at_least_10": df[
            df["osm_building_count"] >= 10
        ],
        "official_at_least_100": df[
            df["official_total"] >= 100
        ],
        "osm_10_official_100": df[
            (df["osm_building_count"] >= 10)
            & (df["official_total"] >= 100)
        ],
    }

    results = []

    for name, subset in scenarios.items():
        print(f"\nSENARYO: {name}")
        print("Mahalle:", len(subset))
        print(
            "Resmi kayit:",
            int(subset["official_total"].sum())
        )
        print(
            "OSM binasi:",
            int(subset["osm_building_count"].sum())
        )

        results.extend(
            calculate_correlations(subset, name)
        )

    result = pd.DataFrame(results)

    print("\nKORELASYON KARSILASTIRMASI:")
    print(
        result[
            [
                "scenario",
                "feature",
                "n",
                "spearman_rho",
                "p_value",
            ]
        ].round(4).to_string(index=False)
    )

    print("\nOSM BINA SAYISI ICIN OZET:")

    count_results = result[
        result["feature"] == "osm_building_count"
    ]

    print(
        count_results[
            ["scenario", "n", "spearman_rho", "p_value"]
        ].round(4).to_string(index=False)
    )

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig"
    )

    print("\nKAYDEDILDI:", OUTPUT)


if __name__ == "__main__":
    main()
