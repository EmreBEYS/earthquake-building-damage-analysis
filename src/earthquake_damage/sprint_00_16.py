"""Repeatable, leakage-aware evaluation of preserved Sprint 00-10 models."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import accuracy_score, f1_score, log_loss
from sklearn.model_selection import GroupShuffleSplit, train_test_split

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sprint_00_16.json"


class ModelEvaluationError(RuntimeError):
    """Raised when model evaluation inputs or invariants are invalid."""


@dataclass(frozen=True)
class EvaluationInputs:
    frame: pd.DataFrame
    spatial_frame: pd.DataFrame
    models: dict[str, Any]
    model_evidence: dict[str, dict[str, Any]]
    reported_metrics: pd.DataFrame


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ModelEvaluationError(f"Could not read Sprint 00-16 config: {error}") from error


def audit_feature_contract(columns: Iterable[str], target: str) -> dict[str, Any]:
    """Flag identifiers and target-derived fields if they enter model features."""
    feature_columns = [str(column) for column in columns]
    forbidden_exact = {
        target,
        "damage_grade",
        "damage_label",
        "damage_binary",
        "hasar_durumu",
        "hasar_durumu_original",
        "quality_status",
        "source_page",
        "source_pdf",
    }
    identifier_tokens = ("_id", "identifier", "source_")
    forbidden = sorted(
        column
        for column in feature_columns
        if column in forbidden_exact
        or any(token in column.casefold() for token in identifier_tokens)
    )
    return {
        "feature_columns": feature_columns,
        "forbidden_feature_columns": forbidden,
        "target_in_features": target in feature_columns,
        "passed": not forbidden and target not in feature_columns,
    }


def bootstrap_macro_f1(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    *,
    labels: list[str],
    iterations: int,
    random_state: int,
) -> dict[str, float]:
    """Return a deterministic percentile interval for macro-F1."""
    if len(y_true) != len(y_pred) or not len(y_true):
        raise ModelEvaluationError("Bootstrap inputs must be non-empty and equally sized")
    generator = np.random.default_rng(random_state)
    scores = []
    for _ in range(iterations):
        indices = generator.integers(0, len(y_true), size=len(y_true))
        scores.append(
            f1_score(
                y_true[indices],
                y_pred[indices],
                labels=labels,
                average="macro",
                zero_division=0,
            )
        )
    lower, median, upper = np.percentile(scores, [2.5, 50, 97.5])
    return {
        "lower_95": float(lower),
        "median": float(median),
        "upper_95": float(upper),
    }


def probability_uncertainty(
    model: Any,
    features: pd.DataFrame,
    y_true: np.ndarray,
    *,
    low_confidence_threshold: float,
) -> dict[str, float] | None:
    """Summarize predictive entropy and confidence without claiming calibration."""
    if not hasattr(model, "predict_proba"):
        return None
    probabilities = np.asarray(model.predict_proba(features), dtype=float)
    probabilities = np.clip(probabilities, 1e-15, 1.0)
    class_count = probabilities.shape[1]
    entropy = -(probabilities * np.log(probabilities)).sum(axis=1) / math.log(class_count)
    max_probability = probabilities.max(axis=1)
    return {
        "mean_normalized_entropy": float(entropy.mean()),
        "median_max_probability": float(np.median(max_probability)),
        "low_confidence_fraction": float(
            np.mean(max_probability < low_confidence_threshold)
        ),
        "multiclass_log_loss": float(log_loss(y_true, probabilities, labels=model.classes_)),
    }


def _load_inputs(project_root: Path, config: dict[str, Any]) -> EvaluationInputs:
    dataset_path = project_root / config["dataset"]
    spatial_path = project_root / config["spatial_layer"]
    report_path = project_root / config["reported_metrics"]
    frame = pd.read_csv(dataset_path)
    required = {
        config["id_column"],
        config["target"],
        *config["features"],
    }
    missing = required.difference(frame.columns)
    if missing:
        raise ModelEvaluationError(f"Dataset is missing columns: {sorted(missing)}")
    if not frame[config["id_column"]].is_unique:
        raise ModelEvaluationError("Building identifiers must be unique")
    frame = frame.dropna(subset=list(required)).copy()

    try:
        import geopandas as gpd
    except ImportError as error:
        raise ModelEvaluationError("GeoPandas is required for the spatial split") from error
    spatial = gpd.read_parquet(spatial_path)[[config["spatial_id_column"], "geometry"]]
    spatial = spatial.rename(columns={config["spatial_id_column"]: config["id_column"]})
    spatial = spatial.to_crs("EPSG:32637")
    centroids = spatial.geometry.centroid
    spatial["spatial_group"] = (
        (centroids.x // config["spatial_grid_metres"]).astype(int).astype(str)
        + "_"
        + (centroids.y // config["spatial_grid_metres"]).astype(int).astype(str)
    )
    spatial_frame = frame.merge(
        spatial[[config["id_column"], "spatial_group"]],
        on=config["id_column"],
        how="inner",
        validate="one_to_one",
    )
    if spatial_frame.empty:
        raise ModelEvaluationError("Spatial layer did not match any evaluation records")

    models: dict[str, Any] = {}
    model_evidence: dict[str, dict[str, Any]] = {}
    for name in config["models"]:
        path = project_root / config["model_directory"] / f"{name}.joblib"
        model_evidence[name] = {
            "path": path.relative_to(project_root).as_posix(),
            "sha256_before": file_sha256(path),
            "mtime_ns_before": path.stat().st_mtime_ns,
        }
        models[name] = joblib.load(path)
    reported_metrics = pd.read_csv(report_path)
    return EvaluationInputs(frame, spatial_frame, models, model_evidence, reported_metrics)


def _split_indices(
    frame: pd.DataFrame, config: dict[str, Any], *, spatial: bool
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    if spatial:
        splitter = GroupShuffleSplit(
            n_splits=1,
            test_size=config["test_size"],
            random_state=config["random_state"],
        )
        train, test = next(
            splitter.split(frame, frame[config["target"]], frame["spatial_group"])
        )
        train_groups = set(frame.iloc[train]["spatial_group"])
        test_groups = set(frame.iloc[test]["spatial_group"])
        evidence = {
            "method": "group_shuffle_split_1km_grid",
            "train_groups": len(train_groups),
            "test_groups": len(test_groups),
            "group_overlap": len(train_groups & test_groups),
        }
        return np.asarray(train), np.asarray(test), evidence
    indices = np.arange(len(frame))
    train, test = train_test_split(
        indices,
        test_size=config["test_size"],
        random_state=config["random_state"],
        stratify=frame[config["target"]],
    )
    return np.asarray(train), np.asarray(test), {"method": "stratified_random"}


def _duplicate_feature_overlap(
    train: pd.DataFrame, test: pd.DataFrame, features: list[str]
) -> int:
    train_values = set(map(tuple, train[features].drop_duplicates().to_numpy()))
    test_values = set(map(tuple, test[features].drop_duplicates().to_numpy()))
    return len(train_values & test_values)


def _evaluate_split(
    inputs: EvaluationInputs,
    config: dict[str, Any],
    *,
    split_name: str,
    spatial: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    frame = inputs.spatial_frame if spatial else inputs.frame
    train_idx, test_idx, split_evidence = _split_indices(frame, config, spatial=spatial)
    train = frame.iloc[train_idx]
    test = frame.iloc[test_idx]
    features = config["features"]
    target = config["target"]
    labels = sorted(frame[target].unique().tolist())
    id_column = config["id_column"]
    id_overlap = set(train[id_column]) & set(test[id_column])
    split_evidence.update(
        {
            "train_rows": len(train),
            "test_rows": len(test),
            "record_id_overlap": len(id_overlap),
            "exact_feature_vector_overlap": _duplicate_feature_overlap(
                train, test, features
            ),
            "test_class_counts": {
                key: int(value) for key, value in test[target].value_counts().items()
            },
        }
    )

    metrics: list[dict[str, Any]] = []
    uncertainty_rows: list[dict[str, Any]] = []
    for model_index, (name, preserved_model) in enumerate(inputs.models.items()):
        model = clone(preserved_model) if spatial else preserved_model
        if spatial:
            model.fit(train[features], train[target])
        predictions = np.asarray(model.predict(test[features]))
        truth = test[target].to_numpy()
        interval = bootstrap_macro_f1(
            truth,
            predictions,
            labels=labels,
            iterations=config["bootstrap_iterations"],
            random_state=config["random_state"] + model_index,
        )
        row = {
            "split": split_name,
            "model": name,
            "train_rows": len(train),
            "test_rows": len(test),
            "accuracy": float(accuracy_score(truth, predictions)),
            "macro_f1": float(
                f1_score(truth, predictions, labels=labels, average="macro", zero_division=0)
            ),
            "weighted_f1": float(
                f1_score(
                    truth, predictions, labels=labels, average="weighted", zero_division=0
                )
            ),
            "macro_f1_ci_lower": interval["lower_95"],
            "macro_f1_ci_upper": interval["upper_95"],
        }
        metrics.append(row)
        uncertainty = probability_uncertainty(
            model,
            test[features],
            truth,
            low_confidence_threshold=config["low_confidence_threshold"],
        )
        if uncertainty is not None:
            uncertainty_rows.append({"split": split_name, "model": name, **uncertainty})
    return metrics, split_evidence, uncertainty_rows


def _markdown_report(report: dict[str, Any]) -> str:
    metrics = pd.DataFrame(report["model_metrics"])
    table = metrics[
        [
            "split",
            "model",
            "accuracy",
            "macro_f1",
            "weighted_f1",
            "macro_f1_ci_lower",
            "macro_f1_ci_upper",
        ]
    ].copy()
    for column in table.columns[2:]:
        table[column] = table[column].map(lambda value: f"{value:.4f}")
    headers = table.columns.tolist()
    markdown_rows = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |",
    ]
    markdown_rows.extend(
        "| " + " | ".join(str(value) for value in row) + " |"
        for row in table.itertuples(index=False, name=None)
    )
    lines = [
        "# Sprint 00-16 — Mevcut Modellerin Değerlendirilmesi",
        "",
        "## Sonuç",
        "",
        report["conclusion"],
        "",
        "## Model karşılaştırması",
        "",
        *markdown_rows,
        "",
        "## Veri sızıntısı denetimi",
        "",
        f"- Özellik sözleşmesi geçti: `{report['leakage_audit']['feature_contract']['passed']}`",
        f"- Random split kimlik kesişimi: `{report['leakage_audit']['random_split']['record_id_overlap']}`",
        f"- Spatial split kimlik kesişimi: `{report['leakage_audit']['spatial_split']['record_id_overlap']}`",
        f"- Spatial grup kesişimi: `{report['leakage_audit']['spatial_split']['group_overlap']}`",
        f"- Model artefaktları değişmedi: `{report['model_preservation']['all_preserved']}`",
        "",
        "## Sınıf dengesizliği ve belirsizlik",
        "",
        f"- Çoğunluk/azınlık oranı: `{report['class_imbalance']['majority_to_minority_ratio']:.2f}`",
        f"- Sınıf sayısı: `{len(report['class_imbalance']['counts'])}`",
        "- Macro-F1 güven aralıkları 300 bootstrap tekrarından türetilmiştir.",
        "- Tahmin entropisi ve düşük güven oranı tanılayıcıdır; kalibrasyon garantisi değildir.",
        "",
        "## Yorum sınırları",
        "",
        "- Copernicus sınıfları resmî bina güvenliği kararı değildir.",
        "- Spatial split genelleme stres testidir; tek bir coğrafi bölme nihai kanıt değildir.",
        "- Düşük macro-F1, çoğunluk sınıfı doğruluğunun azınlık sınıflarındaki zayıflığı gizlediğini gösterir.",
        "",
    ]
    return "\n".join(lines)


def evaluate_existing_models(
    project_root: Path = PROJECT_ROOT,
    output_root: Path | None = None,
    config_path: Path | None = None,
) -> dict[str, Any]:
    """Evaluate saved models without overwriting them and write the Sprint report."""
    config_source = config_path or project_root / "configs" / "sprint_00_16.json"
    config = load_config(config_source)
    inputs = _load_inputs(project_root, config)
    feature_contract = audit_feature_contract(config["features"], config["target"])
    if not feature_contract["passed"]:
        raise ModelEvaluationError("Feature contract failed leakage checks")

    random_metrics, random_evidence, random_uncertainty = _evaluate_split(
        inputs, config, split_name="stratified_random", spatial=False
    )
    spatial_metrics, spatial_evidence, spatial_uncertainty = _evaluate_split(
        inputs, config, split_name="spatial_1km_groups", spatial=True
    )
    reported = inputs.reported_metrics.set_index("model")
    random_metric_match = all(
        abs(row["macro_f1"] - float(reported.loc[row["model"], "macro_f1"])) < 1e-12
        and abs(row["accuracy"] - float(reported.loc[row["model"], "accuracy"])) < 1e-12
        for row in random_metrics
    )

    target = config["target"]
    counts = inputs.frame[target].value_counts()
    model_preservation: dict[str, Any] = {}
    for name, evidence in inputs.model_evidence.items():
        path = project_root / evidence["path"]
        after_hash = file_sha256(path)
        after_mtime = path.stat().st_mtime_ns
        model_preservation[name] = {
            **evidence,
            "sha256_after": after_hash,
            "mtime_ns_after": after_mtime,
            "preserved": after_hash == evidence["sha256_before"]
            and after_mtime == evidence["mtime_ns_before"],
        }
    all_preserved = all(item["preserved"] for item in model_preservation.values())
    if not all_preserved:
        raise ModelEvaluationError("A saved model artifact changed during evaluation")

    metrics = random_metrics + spatial_metrics
    best_spatial = max(spatial_metrics, key=lambda row: row["macro_f1"])
    report = {
        "sprint": "00-16",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation_scope": "exploratory_reproducibility_and_generalization_audit",
        "conclusion": (
            f"Spatial değerlendirmede en yüksek macro-F1 {best_spatial['model']} için "
            f"{best_spatial['macro_f1']:.4f}. Hiçbir model operasyonel hasar sınıflandırması "
            "için yeterli kanıt sunmuyor; azınlık sınıfları ve coğrafi genelleme zayıf."
        ),
        "dataset": {
            "rows": len(inputs.frame),
            "spatially_matched_rows": len(inputs.spatial_frame),
            "features": config["features"],
            "target": target,
            "sha256": file_sha256(project_root / config["dataset"]),
        },
        "model_metrics": metrics,
        "reported_random_metrics_reproduced": random_metric_match,
        "leakage_audit": {
            "feature_contract": feature_contract,
            "random_split": random_evidence,
            "spatial_split": spatial_evidence,
        },
        "class_imbalance": {
            "counts": {key: int(value) for key, value in counts.items()},
            "shares": {key: float(value / counts.sum()) for key, value in counts.items()},
            "majority_to_minority_ratio": float(counts.max() / counts.min()),
        },
        "uncertainty": random_uncertainty + spatial_uncertainty,
        "model_preservation": {"all_preserved": all_preserved, "models": model_preservation},
        "limitations": [
            "Copernicus labels are mapped-damage observations, not official safety decisions.",
            "Two source records lack valid Sprint 00-14 polygon geometry and are excluded from the spatial split.",
            "Bootstrap intervals quantify resampling variation, not deployment uncertainty.",
            "One spatial holdout is a stress test and does not establish external validity.",
        ],
    }

    destination = output_root or project_root / config["output_root"]
    destination.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(metrics).to_csv(destination / "model_comparison.csv", index=False)
    pd.DataFrame(report["uncertainty"]).to_csv(
        destination / "uncertainty_summary.csv", index=False
    )
    pd.DataFrame(
        [
            {"damage_class": key, "records": int(value), "share": float(value / counts.sum())}
            for key, value in counts.items()
        ]
    ).to_csv(destination / "class_distribution.csv", index=False)
    (destination / "model_evaluation_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (destination / "model_evaluation_report.md").write_text(
        _markdown_report(report), encoding="utf-8"
    )
    return report

