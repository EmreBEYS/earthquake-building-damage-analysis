
from pathlib import Path
import json

import joblib
import pandas as pd

from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


ROOT = Path(__file__).resolve().parents[2]

DATASET = (
    ROOT / "data" / "processed"
    / "building_features.csv"
)

REPORT_DIR = ROOT / "reports" / "sprint_00-10"
MODEL_DIR = ROOT / "models"

FEATURES = [
    "building_area_m2",
    "building_perimeter_m",
    "shape_index",
]

TARGET = "damage_class"
RANDOM_STATE = 42


def load_data():
    df = pd.read_csv(DATASET)

    required = FEATURES + [TARGET]
    missing = [
        column for column in required
        if column not in df.columns
    ]

    if missing:
        raise ValueError(f"Eksik sutunlar: {missing}")

    df = df.dropna(subset=required).copy()

    if not df["building_id"].is_unique:
        raise ValueError("Tekrarlanan building_id var")

    X = df[FEATURES]
    y = df[TARGET]

    return X, y


def build_models():
    return {
        "dummy": DummyClassifier(
            strategy="most_frequent"
        ),
        "logistic_regression": make_pipeline(
            StandardScaler(),
            LogisticRegression(
                max_iter=3000,
                class_weight="balanced",
                random_state=RANDOM_STATE
            )
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=300,
            class_weight="balanced_subsample",
            random_state=RANDOM_STATE,
            n_jobs=-1
        ),
    }


def main():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    X, y = load_data()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        random_state=RANDOM_STATE,
        stratify=y
    )

    print("=== MODEL EGITIMI ===")
    print(f"Egitim: {len(X_train)}")
    print(f"Test: {len(X_test)}")

    results = []
    labels = sorted(y.unique())

    for name, model in build_models().items():
        print(f"\n=== {name} ===")

        model.fit(X_train, y_train)
        predictions = model.predict(X_test)

        accuracy = accuracy_score(
            y_test, predictions
        )
        macro_f1 = f1_score(
            y_test,
            predictions,
            average="macro",
            zero_division=0
        )
        weighted_f1 = f1_score(
            y_test,
            predictions,
            average="weighted",
            zero_division=0
        )

        print(f"Accuracy: {accuracy:.4f}")
        print(f"Macro F1: {macro_f1:.4f}")
        print(f"Weighted F1: {weighted_f1:.4f}")

        report = classification_report(
            y_test,
            predictions,
            labels=labels,
            zero_division=0
        )
        print(report)

        matrix = confusion_matrix(
            y_test,
            predictions,
            labels=labels
        )

        pd.DataFrame(
            matrix,
            index=labels,
            columns=labels
        ).to_csv(
            REPORT_DIR / f"{name}_confusion_matrix.csv"
        )

        with open(
            REPORT_DIR / f"{name}_report.txt",
            "w",
            encoding="utf-8"
        ) as file:
            file.write(report)

        results.append({
            "model": name,
            "accuracy": accuracy,
            "macro_f1": macro_f1,
            "weighted_f1": weighted_f1,
        })

        joblib.dump(
            model,
            MODEL_DIR / f"{name}.joblib"
        )

    results_df = pd.DataFrame(results)
    results_df.to_csv(
        REPORT_DIR / "model_comparison.csv",
        index=False
    )

    print("\n=== MODEL KARSILASTIRMASI ===")
    print(
        results_df.sort_values(
            "macro_f1",
            ascending=False
        ).to_string(index=False)
    )

    with open(
        REPORT_DIR / "experiment_config.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            {
                "dataset": str(DATASET.relative_to(ROOT)),
                "features": FEATURES,
                "target": TARGET,
                "random_state": RANDOM_STATE,
                "test_size": 0.20,
                "split_method": "stratified_random",
                "evaluation_scope": "exploratory",
            },
            file,
            indent=2
        )


if __name__ == "__main__":
    main()
