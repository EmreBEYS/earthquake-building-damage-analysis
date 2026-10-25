from pathlib import Path

import pandas as pd
import pytest

from earthquake_damage.dashboard_data import (
    DashboardDataError,
    aggregate_damage_distribution,
    load_dashboard_reports,
    read_csv_checked,
)


def test_committed_dashboard_reports_are_complete() -> None:
    reports = load_dashboard_reports()
    assert set(reports) == {
        "damage_distribution",
        "v1_models",
        "v2_models",
        "v3_neighborhoods",
        "v3_correlations",
        "v3_model_summary",
    }
    assert len(reports["v3_neighborhoods"]) == 62


def test_damage_distribution_total_matches_validated_report() -> None:
    reports = load_dashboard_reports()
    distribution = aggregate_damage_distribution(reports["damage_distribution"])
    assert int(distribution["records"].sum()) == 46_563


def test_read_csv_checked_reports_missing_columns(tmp_path: Path) -> None:
    path = tmp_path / "report.csv"
    pd.DataFrame({"available": [1]}).to_csv(path, index=False)

    with pytest.raises(DashboardDataError, match="gerekli"):
        read_csv_checked(path, {"required"})
