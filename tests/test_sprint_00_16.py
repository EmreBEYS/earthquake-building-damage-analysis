import json
from pathlib import Path

import numpy as np

from earthquake_damage.sprint_00_16 import (
    audit_feature_contract,
    bootstrap_macro_f1,
)

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "sprint_00-16"


def test_feature_contract_rejects_target_and_identifier() -> None:
    audit = audit_feature_contract(
        ["building_area_m2", "damage_class", "building_id"], "damage_class"
    )
    assert audit["passed"] is False
    assert audit["target_in_features"] is True
    assert audit["forbidden_feature_columns"] == ["building_id", "damage_class"]


def test_feature_contract_accepts_geometry_features() -> None:
    audit = audit_feature_contract(
        ["building_area_m2", "building_perimeter_m", "shape_index"], "damage_class"
    )
    assert audit["passed"] is True
    assert audit["forbidden_feature_columns"] == []


def test_bootstrap_macro_f1_is_deterministic_and_bounded() -> None:
    truth = np.array(["a", "a", "b", "b", "c", "c"])
    prediction = np.array(["a", "b", "b", "b", "c", "a"])
    first = bootstrap_macro_f1(
        truth, prediction, labels=["a", "b", "c"], iterations=50, random_state=42
    )
    second = bootstrap_macro_f1(
        truth, prediction, labels=["a", "b", "c"], iterations=50, random_state=42
    )
    assert first == second
    assert 0 <= first["lower_95"] <= first["median"] <= first["upper_95"] <= 1


def test_committed_model_evaluation_report_contract() -> None:
    report = json.loads(
        (REPORT_ROOT / "model_evaluation_report.json").read_text(encoding="utf-8")
    )
    assert report["sprint"] == "00-16"
    assert report["dataset"]["rows"] == 3_619
    assert report["dataset"]["spatially_matched_rows"] == 3_617
    assert report["reported_random_metrics_reproduced"] is True
    assert report["model_preservation"]["all_preserved"] is True
    assert report["leakage_audit"]["feature_contract"]["passed"] is True
    assert report["leakage_audit"]["random_split"]["record_id_overlap"] == 0
    assert report["leakage_audit"]["spatial_split"]["record_id_overlap"] == 0
    assert report["leakage_audit"]["spatial_split"]["group_overlap"] == 0
    assert {row["model"] for row in report["model_metrics"]} == {
        "dummy",
        "logistic_regression",
        "random_forest",
    }
    assert {row["split"] for row in report["model_metrics"]} == {
        "stratified_random",
        "spatial_1km_groups",
    }
    assert len(report["model_metrics"]) == 6
    assert len(report["uncertainty"]) == 6
    assert (REPORT_ROOT / "model_evaluation_report.md").is_file()

