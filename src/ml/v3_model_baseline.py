
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from sklearn.cluster import KMeans
from sklearn.dummy import DummyRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]

DATA_FILE = (
    ROOT / "reports/sprint_00-10"
    / "v3_high_coverage_analysis.csv"
)

GEO_FILE = (
    ROOT / "data/processed/aoi_mahalleler.gpkg"
)

OUTPUT_DIR = ROOT / "reports/sprint_00-10"

FEATURES = [
    "osm_buildings_per_km2",
    "osm_median_area_m2",
    "osm_footprint_area_ratio",
]

TARGET = "severe_ratio"

RANDOM_STATE = 42
N_GROUPS = 5


def prepare_data():
    df = pd.read_csv(DATA_FILE)

    geo = gpd.read_file(GEO_FILE)

    geo = geo.to_crs("EPSG:32637")

    if not df["id"].is_unique:
        raise ValueError("Analiz ID degerleri tekil degil")

    if not geo["id"].is_unique:
        raise ValueError("Geometri ID degerleri tekil degil")

    centroids = geo.geometry.centroid

    geo["centroid_x"] = centroids.x
    geo["centroid_y"] = centroids.y

    df = df.merge(
        geo[["id", "centroid_x", "centroid_y"]],
        on="id",
        how="left",
        validate="one_to_one",
    )

    required = FEATURES + [
        TARGET,
        "centroid_x",
        "centroid_y",
        "official_total",
    ]

    if df[required].isna().all(axis=1).any():
        raise ValueError("Tamamen bos analiz satiri")

    if df[["centroid_x", "centroid_y"]].isna().any().any():
        raise ValueError("Eksik mahalle koordinati")

    if df[TARGET].isna().any():
        raise ValueError("Eksik hedef degeri")

    if not df[TARGET].between(0, 1).all():
        raise ValueError("Hasar orani 0-1 disinda")

    for feature in FEATURES:
        df[feature] = pd.to_numeric(
            df[feature],
            errors="coerce",
        )

    df[FEATURES] = df[FEATURES].replace(
        [np.inf, -np.inf],
        np.nan,
    )

    return df


def build_model():
    return Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler", StandardScaler()),
        ("ridge", Ridge(alpha=10.0)),
    ])


def main():
    print("=== V3 MEKANSAL BASELINE DENEYI ===")

    df = prepare_data()

    print("Mahalle:", len(df))
    print("Resmi kayit:", int(df["official_total"].sum()))

    coordinates = df[
        ["centroid_x", "centroid_y"]
    ].to_numpy()

    # Komsu mahalleleri ayni grupta tutmak
    # icin koordinat bazli gruplar.
    clusterer = KMeans(
        n_clusters=N_GROUPS,
        random_state=RANDOM_STATE,
        n_init=10,
    )

    groups = clusterer.fit_predict(coordinates)

    print("\nMEKANSAL GRUP BOYUTLARI:")
    print(pd.Series(groups).value_counts().sort_index())

    X = df[FEATURES]
    y = df[TARGET]

    splitter = GroupKFold(n_splits=N_GROUPS)

    rows = []
    predictions = []

    for fold, (train_idx, test_idx) in enumerate(
        splitter.split(X, y, groups),
        start=1,
    ):
        X_train = X.iloc[train_idx]
        X_test = X.iloc[test_idx]

        y_train = y.iloc[train_idx]
        y_test = y.iloc[test_idx]

        dummy = DummyRegressor(
            strategy="mean"
        )

        ridge = build_model()

        dummy.fit(X_train, y_train)
        ridge.fit(X_train, y_train)

        models = {
            "Dummy": dummy,
            "Ridge": ridge,
        }

        for model_name, model in models.items():
            y_pred = np.clip(
                model.predict(X_test),
                0.0,
                1.0,
            )

            mae = mean_absolute_error(
                y_test,
                y_pred,
            )

            rows.append({
                "fold": fold,
                "model": model_name,
                "train_n": len(train_idx),
                "test_n": len(test_idx),
                "mae": mae,
            })

            for position, index in enumerate(test_idx):
                predictions.append({
                    "id": df.iloc[index]["id"],
                    "mahalle": df.iloc[index]["mahalle"],
                    "fold": fold,
                    "model": model_name,
                    "actual": float(y_test.iloc[position]),
                    "predicted": float(y_pred[position]),
                    "official_total": int(
                        df.iloc[index]["official_total"]
                    ),
                })

    metrics = pd.DataFrame(rows)
    pred_df = pd.DataFrame(predictions)

    print("\nFOLD SONUCLARI:")
    print(
        metrics.round(4).to_string(index=False)
    )

    summary = []

    for model_name, subset in pred_df.groupby("model"):
        mae = mean_absolute_error(
            subset["actual"],
            subset["predicted"],
        )

        weighted_mae = np.average(
            np.abs(
                subset["actual"] - subset["predicted"]
            ),
            weights=subset["official_total"],
        )

        summary.append({
            "model": model_name,
            "mae": mae,
            "weighted_mae": weighted_mae,
        })

    summary = pd.DataFrame(summary)

    print("\nGENEL SONUCLAR:")
    print(
        summary.round(4).to_string(index=False)
    )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    metrics.to_csv(
        OUTPUT_DIR / "v3_model_fold_metrics.csv",
        index=False,
    )

    summary.to_csv(
        OUTPUT_DIR / "v3_model_summary.csv",
        index=False,
    )

    pred_df.to_csv(
        OUTPUT_DIR / "v3_model_predictions.csv",
        index=False,
    )

    print("\nV3 model deneyi tamamlandi.")


if __name__ == "__main__":
    main()
