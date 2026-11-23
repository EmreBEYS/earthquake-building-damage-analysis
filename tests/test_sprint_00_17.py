import hashlib
import json
from pathlib import Path

import geopandas as gpd
import joblib
import pandas as pd
import pytest
from shapely.geometry import Polygon
from sklearn.ensemble import RandomForestClassifier

from earthquake_damage.sprint_00_17 import PredictionMapError, generate_prediction_map


FEATURES = ["building_area_m2", "building_perimeter_m", "shape_index"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _project(tmp_path: Path) -> Path:
    (tmp_path / "configs").mkdir()
    (tmp_path / "models").mkdir()
    (tmp_path / "data" / "processed").mkdir(parents=True)
    geometries = [
        Polygon([(0, 0), (10, 0), (10, 10), (0, 10)]),
        Polygon([(20, 0), (40, 0), (40, 10), (20, 10)]),
        Polygon([(0, 20), (30, 20), (30, 30), (0, 30)]),
        Polygon([(40, 20), (80, 20), (80, 30), (40, 30)]),
    ]
    buildings = gpd.GeoDataFrame(
        {
            "feature_id": ["b1", "b2", "b3", "b4"],
            "damage_grade": ["observed-a", "observed-b", "observed-a", "observed-b"],
        },
        geometry=geometries,
        crs="EPSG:32637",
    )
    buildings.to_parquet(tmp_path / "data" / "processed" / "buildings.parquet")
    metric = buildings.geometry
    area = metric.area
    perimeter = metric.length
    frame = pd.DataFrame(
        {
            "building_area_m2": area,
            "building_perimeter_m": perimeter,
            "shape_index": perimeter / (2 * (3.141592653589793 * area) ** 0.5),
        }
    )
    model = RandomForestClassifier(n_estimators=5, random_state=42).fit(
        frame, ["class-a", "class-b", "class-a", "class-b"]
    )
    model_path = tmp_path / "models" / "random_forest.joblib"
    joblib.dump(model, model_path)
    config = {
        "sprint": "00-17",
        "model_name": "random_forest",
        "model_path": "models/random_forest.joblib",
        "model_sha256": _sha256(model_path),
        "source_layer": "data/processed/buildings.parquet",
        "output_layer": "data/dashboard/sprint_00-17/predicted_damage.geojson",
        "manifest": "data/dashboard/sprint_00-17/manifest.json",
        "id_column": "feature_id",
        "observed_damage_column": "damage_grade",
        "metric_crs": "EPSG:32637",
        "output_crs": "EPSG:4326",
        "features": FEATURES,
        "low_confidence_threshold": 0.6,
    }
    (tmp_path / "configs" / "sprint_00_17.json").write_text(json.dumps(config))
    return tmp_path


def test_generates_probabilities_confidence_and_leakage_evidence(tmp_path: Path) -> None:
    root = _project(tmp_path)
    manifest = generate_prediction_map(root)
    output = json.loads(
        (root / "data/dashboard/sprint_00-17/predicted_damage.geojson").read_text()
    )

    assert manifest["output"]["records"] == 4
    assert manifest["leakage_audit"]["observed_damage_used_for_inference"] is False
    properties = output["features"][0]["properties"]
    assert properties["observed_damage"].startswith("observed-")
    assert properties["predicted_damage"].startswith("class-")
    assert 0 <= properties["confidence"] <= 1
    assert isinstance(properties["low_confidence"], bool)
    assert {key for key in properties if key.startswith("probability_")} == {
        "probability_class_a",
        "probability_class_b",
    }


def test_rejects_a_model_not_evaluated_in_sprint_00_16(tmp_path: Path) -> None:
    root = _project(tmp_path)
    config_path = root / "configs" / "sprint_00_17.json"
    config = json.loads(config_path.read_text())
    config["model_sha256"] = "0" * 64
    config_path.write_text(json.dumps(config))

    with pytest.raises(PredictionMapError, match="SHA-256"):
        generate_prediction_map(root)


def test_rejects_observed_damage_in_feature_contract(tmp_path: Path) -> None:
    root = _project(tmp_path)
    config_path = root / "configs" / "sprint_00_17.json"
    config = json.loads(config_path.read_text())
    config["features"] = ["damage_grade", *FEATURES]
    config_path.write_text(json.dumps(config))

    with pytest.raises(PredictionMapError, match="leakage"):
        generate_prediction_map(root)
