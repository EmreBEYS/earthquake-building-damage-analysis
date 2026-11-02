import json

import pandas as pd
import pytest

from earthquake_damage.sprint_00_15 import (
    RealDamageMapError,
    aggregate_official_records,
    coordinate_evidence_columns,
    load_config,
    load_real_damage_map,
)


def test_committed_real_damage_map_contract() -> None:
    layers = load_real_damage_map()
    assert len(layers.official_neighborhoods["features"]) == 87
    assert len(layers.copernicus_damage["features"]) == 3_617
    assert layers.neighborhood_stats["official_total"].sum() == 46_563
    assert layers.validation["official_class_totals"] == {
        "no_damage": 10_131,
        "slight_damage": 20_706,
        "moderate_damage": 1_593,
        "heavy_damage": 12_276,
        "urgent_demolition": 955,
        "destroyed": 902,
    }
    assert layers.manifest["official_mapping_level"] == "neighborhood"
    assert layers.manifest["official_coordinate_evidence"] is False
    assert layers.manifest["source_separation"]["joined_at_building_level"] is False
    assert layers.validation["sources_joined_at_building_level"] is False
    assert all(
        feature["properties"]["coordinate_evidence"] is False
        and feature["properties"]["mapping_level"] == "neighborhood"
        for feature in layers.official_neighborhoods["features"]
    )


@pytest.mark.parametrize(
    ("columns", "expected"),
    [
        (["mahalle", "sokak", "bina_numarasi"], []),
        (["latitude", "longitude"], ["latitude", "longitude"]),
        (["lat"], []),
        (["geometry"], ["geometry"]),
    ],
)
def test_coordinate_evidence_requires_explicit_geometry_or_pair(
    columns: list[str], expected: list[str]
) -> None:
    assert coordinate_evidence_columns(columns) == expected


def test_aggregate_official_records_rejects_unknown_damage_class() -> None:
    config = load_config()
    records = pd.DataFrame([{"mahalle": "Örnek", "hasar_durumu": "Belirsiz"}])
    with pytest.raises(RealDamageMapError, match="Unknown official damage classes"):
        aggregate_official_records(records, config)


def test_config_is_valid_json_and_exposes_satellite_attribution() -> None:
    config = load_config()
    assert json.loads(json.dumps(config))["sprint"] == "00-15"
    assert config["satellite_basemap"]["provider"] == "Esri World Imagery"
    assert "attribution" in config["satellite_basemap"]
