from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from shapely.geometry import box

from earthquake_damage.ui.overview import (
    DATA_SOURCES,
    OFFICIAL_CLASSES,
    PERIOD_SOURCES,
    assign_districts,
    district_class_summary,
    official_class_summary,
    source_status,
)
from earthquake_damage.ui.theme import (
    format_int,
    format_pct,
    kpi_card_html,
    source_badges_html,
)

ROOT = Path(__file__).resolve().parents[1]
CLASS_KEYS = [key for key, _, _ in OFFICIAL_CLASSES]


def _statistics():
    rows = [
        {"neighborhood_id": "a", **dict(zip(CLASS_KEYS, [10, 5, 1, 2, 1, 1], strict=True))},
        {"neighborhood_id": "b", **dict(zip(CLASS_KEYS, [0, 5, 1, 2, 0, 1], strict=True))},
    ]
    return pd.DataFrame(rows)


def test_official_class_summary_totals_and_shares():
    summary = official_class_summary(_statistics())
    assert [row["key"] for row in summary] == CLASS_KEYS
    assert sum(row["count"] for row in summary) == 29
    assert summary[0]["share"] == pytest.approx(10 / 29)


def test_real_official_totals_match_record_count():
    statistics = pd.read_csv(ROOT / DATA_SOURCES["official"]["path"])
    assert sum(row["count"] for row in official_class_summary(statistics)) == 46563


def test_assign_districts_uses_largest_overlap():
    crs = "EPSG:32637"
    hoods = gpd.GeoDataFrame(
        {"neighborhood_id": ["a", "b"], "mahalle": ["A", "B"]},
        geometry=[box(0, 0, 10, 10), box(10, 0, 20, 10)], crs=crs,
    )
    districts = gpd.GeoDataFrame(
        {"shapeName": ["West", "East"]},
        geometry=[box(-5, -5, 12, 15), box(12, -5, 30, 15)], crs=crs,
    )
    table = assign_districts(hoods, districts).set_index("neighborhood_id")
    assert table.loc["a", "district"] == "West"
    assert table.loc["b", "district"] == "East"
    assert table.loc["b", "district_share"] == pytest.approx(0.8)


def test_assign_districts_rejects_uncovered_neighbourhoods():
    crs = "EPSG:32637"
    hoods = gpd.GeoDataFrame({"neighborhood_id": ["a"], "mahalle": ["A"]},
                             geometry=[box(100, 100, 110, 110)], crs=crs)
    districts = gpd.GeoDataFrame({"shapeName": ["West"]}, geometry=[box(0, 0, 10, 10)], crs=crs)
    with pytest.raises(ValueError, match="outside both districts"):
        assign_districts(hoods, districts)


def test_district_class_summary_requires_full_assignment():
    districts = pd.DataFrame({"neighborhood_id": ["a", "b"], "district": ["X", "Y"]})
    rows = district_class_summary(_statistics(), districts)
    assert {r["district"] for r in rows} == {"X", "Y"}
    assert sum(r["count"] for r in rows) == 29
    with pytest.raises(ValueError, match="no district"):
        district_class_summary(_statistics(), districts.iloc[:1])


def test_committed_district_table_covers_all_neighbourhoods():
    table = pd.read_csv(ROOT / DATA_SOURCES["districts"]["path"])
    assert len(table) == 87
    assert set(table["district"]) == {"Battalgazi", "Yeşilyurt"}
    assert table["district_share"].min() > 0.99


def test_source_registry_and_period_mapping_are_consistent():
    for keys in PERIOD_SOURCES.values():
        assert set(keys) <= set(DATA_SOURCES)
    entry = source_status(ROOT, "official")
    assert entry["available"] and not entry["local_only"] and entry["size_mb"] > 0
    assert source_status(ROOT, "osm_2026")["local_only"]


def test_turkish_number_formatting():
    assert format_int(46563) == "46.563"
    assert format_pct(0.175) == "%17,5"


def test_html_helpers_escape_values():
    card = kpi_card_html("<b>x</b>", "1", "%5", "#fff", "!")
    assert "<b>x</b>" not in card and "&lt;b&gt;" in card
    badges = source_badges_html([
        {"name": "A<", "role": "r", "terms": "t", "sprint": "00", "available": False},
        {"name": "B", "role": "r", "terms": "t", "sprint": "00", "available": True,
         "local_only": True},
    ])
    assert "A&lt;" in badges and "#EF4444" in badges and "#EAB308" in badges
