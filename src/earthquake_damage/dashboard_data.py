"""Validated data-loading helpers for the Sprint 00-11 dashboard."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_ROOT = PROJECT_ROOT / "reports"


class DashboardDataError(RuntimeError):
    """Raised when a committed dashboard input is missing or malformed."""


def read_csv_checked(path: Path, required_columns: set[str]) -> pd.DataFrame:
    """Read a report CSV and validate the columns used by the dashboard."""
    if not path.is_file():
        raise DashboardDataError(
            f"Gerekli rapor bulunamadı: {path}. "
            "Yerel/ham veriler git deposunda bulunmuyor olabilir."
        )

    frame = pd.read_csv(path)
    missing = required_columns.difference(frame.columns)
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise DashboardDataError(f"{path.name} gerekli sütunları içermiyor: {missing_text}")
    return frame


def load_dashboard_reports(report_root: Path = REPORT_ROOT) -> dict[str, pd.DataFrame]:
    """Load the compact, committed outputs that back every dashboard claim."""
    sprint_09 = report_root / "sprint_00-09"
    sprint_10 = report_root / "sprint_00-10"
    return {
        "damage_distribution": read_csv_checked(
            sprint_09 / "damage_class_distribution.csv", {"person"}
        ),
        "v1_models": read_csv_checked(
            sprint_10 / "model_comparison.csv",
            {"model", "accuracy", "macro_f1", "weighted_f1"},
        ),
        "v2_models": read_csv_checked(
            sprint_10 / "official_model_comparison.csv",
            {"model", "accuracy", "macro_f1"},
        ),
        "v3_neighborhoods": read_csv_checked(
            sprint_10 / "v3_high_coverage_analysis.csv",
            {
                "mahalle",
                "official_total",
                "severe_ratio",
                "osm_building_count",
                "osm_buildings_per_km2",
                "aoi_coverage_ratio",
            },
        ),
        "v3_correlations": read_csv_checked(
            sprint_10 / "v3_correlations.csv",
            {"feature", "n", "spearman_rho", "p_value"},
        ),
        "v3_model_summary": read_csv_checked(
            sprint_10 / "v3_model_summary.csv", {"model", "mae", "weighted_mae"}
        ),
    }


def aggregate_damage_distribution(frame: pd.DataFrame) -> pd.DataFrame:
    """Return one row per damage class, summed across extraction groups."""
    values = frame.drop(columns="person").apply(pd.to_numeric, errors="raise").sum()
    return values.rename_axis("damage_class").reset_index(name="records")
