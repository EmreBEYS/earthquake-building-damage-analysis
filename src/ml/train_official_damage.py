
from pathlib import Path

import pandas as pd

from imblearn.over_sampling import RandomOverSampler
from imblearn.pipeline import Pipeline as ImbPipeline

from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    accuracy_score,
    f1_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder


ROOT = Path(__file__).resolve().parents[2]

DATASET = (
    ROOT / "data" / "final"
    / "malatya_damage_analysis_ready.csv"
)

REPORT_DIR = ROOT / "reports" / "sprint_00-10"
FEATURES = ["mahalle"]
TARGET = "hasar_durumu"
SEED = 42


def load_data():
    df = pd.read_csv(DATASET, low_memory=False)

    X = df[FEATURES].copy()
    X["mahalle"] = X["mahalle"].str.strip()

    y = df[TARGET].copy()

    return X, y


def make_preprocessor():
    return ColumnTransformer(
        transformers=[
            (
                "location",
                OneHotEncoder(
                    handle_unknown="ignore",
                    sparse_output=False
                ),
                ["mahalle"]
            )
        ]
    )


def make_models():
    return {
        "dummy": DummyClassifier(
            strategy="most_frequent"
        ),

        "weighted_rf": Pipeline([
            ("preprocess", make_preprocessor()),
            ("model", RandomForestClassifier(
                n_estimators=200,
                class_weight="balanced",
                min_samples_leaf=10,
                random_state=SEED,
                n_jobs=-1
            ))
        ]),

        "oversampled_rf": ImbPipeline([
            ("preprocess", make_preprocessor()),
            ("sampler", RandomOverSampler(
                random_state=SEED
            )),
            ("model", RandomForestClassifier(
                n_estimators=200,
                min_samples_leaf=10,
                random_state=SEED,
                n_jobs=-1
            ))
        ])
    }


def main():
    X, y = load_data()

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.20,
        stratify=y,
        random_state=SEED
    )

    print("=== RESMI HASAR MODELI ===")
    print(f"Egitim kaydi: {len(X_train)}")
    print(f"Test kaydi: {len(X_test)}")

    print("\nEGITIM SINIF DAGILIMI:")
    print(y_train.value_counts())

    results = []
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    for name, model in make_models().items():
        print(f"\n=== {name} ===")

        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)

        accuracy = accuracy_score(y_test, y_pred)

        macro_f1 = f1_score(
            y_test,
            y_pred,
            average="macro",
            zero_division=0
        )

        print(f"Accuracy: {accuracy:.4f}")
        print(f"Macro F1: {macro_f1:.4f}")

        report = classification_report(
            y_test,
            y_pred,
            zero_division=0
        )

        print(report)

        results.append({
            "model": name,
            "accuracy": accuracy,
            "macro_f1": macro_f1
        })

        with open(
            REPORT_DIR / f"official_{name}.txt",
            "w",
            encoding="utf-8"
        ) as file:
            file.write(report)

    comparison = pd.DataFrame(results)

    comparison.to_csv(
        REPORT_DIR / "official_model_comparison.csv",
        index=False
    )

    print("\n=== KARSILASTIRMA ===")
    print(
        comparison.sort_values(
            "macro_f1",
            ascending=False
        ).to_string(index=False)
    )


if __name__ == "__main__":
    main()
