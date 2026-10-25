
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    accuracy_score,
    f1_score,
)
from sklearn.model_selection import GroupShuffleSplit


ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT / "data" / "interim" / "buildings"
    / "EMSR648_AOI05"
    / "EMSR648_AOI05_builtUpA_analysis.geojson"
)

REPORT_DIR = ROOT / "reports" / "sprint_00-10"

FEATURES = [
    "building_area_m2",
    "building_perimeter_m",
    "shape_index",
]

RANDOM_STATE = 42


def prepare_data():
    gdf = gpd.read_file(INPUT)

    metric = gdf.to_crs("EPSG:32637")

    metric["building_area_m2"] = metric.geometry.area
    metric["building_perimeter_m"] = metric.geometry.length

    area = metric["building_area_m2"]
    perimeter = metric["building_perimeter_m"]

    metric["shape_index"] = (
        perimeter / (2 * np.sqrt(np.pi * area))
    )

    centroids = metric.geometry.centroid

    # 1 km x 1 km mekansal bloklar
    metric["grid_x"] = (
        centroids.x // 1000
    ).astype(int)

    metric["grid_y"] = (
        centroids.y // 1000
    ).astype(int)

    metric["spatial_group"] = (
        metric["grid_x"].astype(str)
        + "_"
        + metric["grid_y"].astype(str)
    )

    return metric


def main():
    df = prepare_data()

    X = df[FEATURES]
    y = df["damage_class"]
    groups = df["spatial_group"]

    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=0.20,
        random_state=RANDOM_STATE
    )

    train_idx, test_idx = next(
        splitter.split(X, y, groups)
    )

    X_train = X.iloc[train_idx]
    X_test = X.iloc[test_idx]

    y_train = y.iloc[train_idx]
    y_test = y.iloc[test_idx]

    train_groups = set(groups.iloc[train_idx])
    test_groups = set(groups.iloc[test_idx])

    assert train_groups.isdisjoint(test_groups)

    model = RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced_subsample",
        random_state=RANDOM_STATE,
        n_jobs=-1
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    print("=== MEKANSAL DOGRULAMA ===")

    print(f"Egitim kaydi: {len(X_train)}")
    print(f"Test kaydi: {len(X_test)}")

    print(f"Egitim bloklari: {len(train_groups)}")
    print(f"Test bloklari: {len(test_groups)}")

    print("\nTEST SINIF DAGILIMI:")
    print(y_test.value_counts())

    print("\nACCURACY:")
    print(accuracy_score(y_test, predictions))

    print("\nMACRO F1:")
    print(
        f1_score(
            y_test,
            predictions,
            average="macro",
            zero_division=0
        )
    )

    report = classification_report(
        y_test,
        predictions,
        zero_division=0
    )

    print("\n", report)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    with open(
        REPORT_DIR / "spatial_validation_report.txt",
        "w",
        encoding="utf-8"
    ) as file:
        file.write(report)


if __name__ == "__main__":
    main()
