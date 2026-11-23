"""Leakage-safe building prediction layer generation for Sprint 00-17."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd

from earthquake_damage.sprint_00_16 import audit_feature_contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "configs" / "sprint_00_17.json"


class PredictionMapError(RuntimeError):
    """Raised when prediction inputs violate the Sprint 00-17 contract."""


@dataclass(frozen=True)
class PredictionMap:
    """Validated prediction layer and its machine-readable manifest."""

    predictions: dict[str, Any]
    manifest: dict[str, Any]
    config: dict[str, Any]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PredictionMapError(f"Could not read Sprint 00-17 config: {error}") from error


def _load_model(path: Path, expected_sha256: str) -> Any:
    if not path.is_file():
        raise PredictionMapError(
            f"Saved model not found: {path}. Restore the Sprint 00-16 model artifact; "
            "Sprint 00-17 does not retrain it."
        )
    actual_sha256 = _sha256(path)
    if actual_sha256 != expected_sha256:
        raise PredictionMapError(
            "Saved model SHA-256 does not match the model evaluated in Sprint 00-16: "
            f"expected {expected_sha256}, got {actual_sha256}"
        )
    try:
        return joblib.load(path), actual_sha256
    except Exception as error:  # joblib can surface several deserialization errors
        raise PredictionMapError(f"Could not load saved model: {error}") from error


def _build_features(buildings: Any, *, metric_crs: str) -> pd.DataFrame:
    """Derive the exact Sprint 00-10 feature schema from geometry only."""
    metric = buildings.to_crs(metric_crs)
    area = metric.geometry.area.astype(float)
    perimeter = metric.geometry.length.astype(float)
    shape_index = perimeter / (2 * np.sqrt(math.pi * area))
    features = pd.DataFrame(
        {
            "building_area_m2": area,
            "building_perimeter_m": perimeter,
            "shape_index": shape_index,
        },
        index=buildings.index,
    )
    invalid = ~np.isfinite(features.to_numpy()).all(axis=1) | (area <= 0).to_numpy()
    if invalid.any():
        raise PredictionMapError(f"Invalid geometry-derived features for {int(invalid.sum())} rows")
    return features


def _validate_model_feature_schema(model: Any, expected: list[str]) -> None:
    actual = getattr(model, "feature_names_in_", None)
    if actual is not None and list(actual) != expected:
        raise PredictionMapError(
            f"Saved model feature schema mismatch: expected {expected}, got {list(actual)}"
        )
    count = getattr(model, "n_features_in_", None)
    if count is not None and int(count) != len(expected):
        raise PredictionMapError(
            f"Saved model expects {count} features, but the contract defines {len(expected)}"
        )


def _safe_probability_key(label: Any) -> str:
    text = str(label).strip().casefold().replace(" ", "_").replace("-", "_")
    return "probability_" + "".join(character for character in text if character.isalnum() or character == "_")


def generate_prediction_map(
    project_root: Path = PROJECT_ROOT,
    *,
    config_path: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate predicted_damage.geojson without using observed damage as a feature."""
    try:
        import geopandas as gpd
    except ImportError as error:
        raise PredictionMapError("GeoPandas is required to generate the prediction layer") from error

    config = load_config(config_path or project_root / "configs" / "sprint_00_17.json")
    features = list(config["features"])
    feature_audit = audit_feature_contract(features, config["observed_damage_column"])
    if not feature_audit["passed"]:
        raise PredictionMapError(
            f"Prediction feature contract contains leakage-prone fields: "
            f"{feature_audit['forbidden_feature_columns']}"
        )
    expected_features = [
        "building_area_m2",
        "building_perimeter_m",
        "shape_index",
    ]
    if features != expected_features:
        raise PredictionMapError(
            f"Sprint 00-16 feature order must remain {expected_features}; got {features}"
        )

    source_path = project_root / config["source_layer"]
    if not source_path.is_file():
        raise PredictionMapError(f"Building source layer not found: {source_path}")
    buildings = gpd.read_parquet(source_path)
    required = {config["id_column"], config["observed_damage_column"], "geometry"}
    missing = required.difference(buildings.columns)
    if missing:
        raise PredictionMapError(f"Building source layer is missing columns: {sorted(missing)}")
    if buildings.crs is None:
        raise PredictionMapError("Building source layer has no CRS")
    if buildings[config["id_column"]].isna().any() or not buildings[config["id_column"]].is_unique:
        raise PredictionMapError("Building identifiers must be present and unique")
    unsafe_geometry = buildings.geometry.isna() | buildings.geometry.is_empty | ~buildings.geometry.is_valid
    if unsafe_geometry.any():
        raise PredictionMapError(f"Unsafe building geometries: {int(unsafe_geometry.sum())}")

    model_path = project_root / config["model_path"]
    model, model_sha256 = _load_model(model_path, config["model_sha256"])
    _validate_model_feature_schema(model, features)
    model_features = _build_features(buildings, metric_crs=config["metric_crs"])[features]

    predictions = np.asarray(model.predict(model_features), dtype=str)
    if len(predictions) != len(buildings):
        raise PredictionMapError("Model returned a different number of predictions than buildings")

    result = buildings[[config["id_column"], config["observed_damage_column"], "geometry"]].copy()
    result = result.rename(columns={config["observed_damage_column"]: "observed_damage"})
    result["predicted_damage"] = predictions
    result["model_name"] = config["model_name"]
    result["model_sha256"] = model_sha256

    probability_columns: list[str] = []
    if hasattr(model, "predict_proba"):
        probabilities = np.asarray(model.predict_proba(model_features), dtype=float)
        classes = [str(value) for value in model.classes_]
        if probabilities.shape != (len(result), len(classes)):
            raise PredictionMapError("predict_proba returned an invalid matrix shape")
        if not np.isfinite(probabilities).all() or not np.allclose(probabilities.sum(axis=1), 1.0):
            raise PredictionMapError("predict_proba returned invalid class probabilities")
        for index, label in enumerate(classes):
            column = _safe_probability_key(label)
            result[column] = probabilities[:, index]
            probability_columns.append(column)
        result["confidence"] = probabilities.max(axis=1)
        result["low_confidence"] = result["confidence"] < float(
            config["low_confidence_threshold"]
        )
    else:
        result["confidence"] = np.nan
        result["low_confidence"] = True

    result = result.to_crs(config["output_crs"])
    destination = output_path or project_root / config["output_layer"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    result.to_file(destination, driver="GeoJSON", index=False)

    manifest = {
        "sprint": config["sprint"],
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": {
            "name": config["model_name"],
            "path": config["model_path"],
            "sha256": model_sha256,
            "feature_schema": features,
        },
        "input": {
            "path": config["source_layer"],
            "sha256": _sha256(source_path),
            "records": len(buildings),
        },
        "output": {
            "path": destination.relative_to(project_root).as_posix()
            if destination.is_relative_to(project_root)
            else str(destination),
            "records": len(result),
            "sha256": _sha256(destination),
            "probability_columns": probability_columns,
            "low_confidence_records": int(result["low_confidence"].sum()),
            "low_confidence_threshold": config["low_confidence_threshold"],
        },
        "leakage_audit": {
            "passed": feature_audit["passed"],
            "model_inputs": features,
            "observed_damage_used_for_inference": False,
            "observed_damage_role": "display_and_comparison_only",
        },
        "limitations": [
            "Predictions are exploratory and are not official building-safety decisions.",
            "Sprint 00-16 found weak minority-class and spatial generalization performance.",
            "Confidence is an uncalibrated model probability and not a safety guarantee.",
        ],
    }
    manifest_path = project_root / config["manifest"]
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def load_prediction_map(project_root: Path = PROJECT_ROOT) -> PredictionMap:
    """Load and validate committed/local Sprint 00-17 dashboard artifacts."""
    config = load_config(project_root / "configs" / "sprint_00_17.json")
    layer_path = project_root / config["output_layer"]
    manifest_path = project_root / config["manifest"]
    if not layer_path.is_file() or not manifest_path.is_file():
        raise PredictionMapError(
            "Sprint 00-17 prediction artifacts are missing. Run "
            "`python scripts/15_generate_prediction_map.py` with the verified saved model."
        )
    try:
        predictions = json.loads(layer_path.read_text(encoding="utf-8"))
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PredictionMapError(f"Could not read prediction artifacts: {error}") from error
    if len(predictions.get("features", [])) != manifest.get("output", {}).get("records"):
        raise PredictionMapError("Prediction layer record count does not match its manifest")
    if _sha256(layer_path) != manifest.get("output", {}).get("sha256"):
        raise PredictionMapError("Prediction layer SHA-256 does not match its manifest")
    return PredictionMap(predictions=predictions, manifest=manifest, config=config)
