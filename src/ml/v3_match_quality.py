
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT / "reports" / "sprint_00-10"
    / "v3_building_match_candidates.csv"
)

OUTPUT_DIR = ROOT / "reports" / "sprint_00-10"


def main():
    df = pd.read_csv(INPUT)

    print("=== V3 ESLESME KALITESI ===")
    print(f"Toplam aday cift: {len(df)}")

    osm_counts = df.groupby("osm_key").size()
    cems_counts = df.groupby("building_id").size()

    print("\nBENZERSIZ KAYITLAR:")
    print("OSM:", len(osm_counts))
    print("Copernicus:", len(cems_counts))

    print("\nCOKLU ESLESME:")
    print(
        "Birden fazla Copernicus ile eslesen OSM:",
        (osm_counts > 1).sum()
    )
    print(
        "Birden fazla OSM ile eslesen Copernicus:",
        (cems_counts > 1).sum()
    )

    df["osm_candidate_count"] = (
        df["osm_key"].map(osm_counts)
    )

    df["cems_candidate_count"] = (
        df["building_id"].map(cems_counts)
    )

    # Yalnizca tek adayli ciftleri ayir.
    one_to_one = df[
        (df["osm_candidate_count"] == 1)
        & (df["cems_candidate_count"] == 1)
    ].copy()

    print("\nTEK ADAYLI CIFTLER:")
    print(len(one_to_one))

    print("\nTEK ADAYLI IOU DAGILIMI:")
    print(one_to_one["iou"].describe())

    for threshold in [0.3, 0.5, 0.7]:
        selected = one_to_one[
            one_to_one["iou"] >= threshold
        ]

        print(
            f"Tek adayli IoU >= {threshold}:",
            len(selected)
        )

    # Bunlar otomatik onayli bina eslesmeleri
    # degildir. Manuel inceleme adaylaridir.
    review = one_to_one[
        (one_to_one["iou"] >= 0.5)
        & (one_to_one["osm_coverage"] >= 0.7)
        & (one_to_one["cems_coverage"] >= 0.7)
    ].copy()

    print("\nYUKSEK ORTUSMELI INCELEME ADAYI:")
    print(len(review))

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    review.to_csv(
        OUTPUT_DIR / "v3_high_overlap_review.csv",
        index=False
    )

    print("\nEN YUKSEK IOU DEGERLERI:")
    print(
        df.nlargest(10, "iou")[
            [
                "osm_key",
                "building_id",
                "iou",
                "osm_coverage",
                "cems_coverage",
                "centroid_distance_m",
            ]
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
