import json
from pathlib import Path

import pytest

from earthquake_damage.geospatial_layers import (
    GeospatialLayerError,
    filter_feature_collection,
    load_map_layers,
    normalize_match_key,
    normalize_neighborhood_name,
    validate_geojson,
)


def polygon_feature(properties: dict, *, feature_id: str = "one") -> dict:
    return {
        "type": "Feature",
        "id": feature_id,
        "properties": properties,
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[38.2, 38.3], [38.3, 38.3], [38.3, 38.4], [38.2, 38.3]]],
        },
    }


def test_committed_map_layers_pass_contract() -> None:
    layers = load_map_layers()
    assert len(layers.neighborhoods["features"]) == 87
    assert len(layers.requested_boundaries["features"]) == 27
    assert len(layers.damage_polygons["features"]) == 3_617
    assert (
        layers.validation["checks"]["copernicus_damage_polygons"]["source_feature_count"] == 3_619
    )
    assert layers.validation["valid"] is True
    assert layers.manifest["official_record_semantics"].startswith("neighborhood aggregates")
    assert len(layers.official_coverage) == 87
    assert sum(row["official_total"] for row in layers.official_coverage) == 46_563
    assert layers.unmapped_official == []
    neighborhood_audit = layers.validation["checks"]["aoi05_neighborhoods"]
    assert neighborhood_audit["exact_match_neighborhoods"] == 80
    assert neighborhood_audit["confirmed_alias_count"] == 7
    assert neighborhood_audit["confirmed_alias_records"] == 2_737
    assert neighborhood_audit["building_level_geolocation_claimed"] is False
    requested_audit = layers.validation["checks"]["requested_neighborhood_boundaries"]
    assert requested_audit["status_counts"] == {
        "confirmed_name_alias": 7,
        "existing_official_match": 18,
        "reference_only": 2,
    }


def test_confirmed_neighborhood_aliases_are_unique_and_explicit() -> None:
    config_path = Path(__file__).resolve().parents[1] / "configs" / "neighborhood_aliases.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))
    aliases = config["aliases"]
    assert len(aliases) == 7
    assert len({normalize_match_key(item["source_name"]) for item in aliases}) == 7
    assert len({item["target_relation_id"] for item in aliases}) == 7
    hamidiye = next(item for item in aliases if item["source_name"] == "HAMDIYE")
    assert hamidiye["target_relation_id"] == "relation/12268774"
    assert hamidiye["district"] == "Yeşilyurt"
    assert config["record_geography"] == "neighborhood_aggregate_not_building_geolocation"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Çöşnük Mahallesi", "cosnuk"), ("  ŞEYH BAYRAM  ", "seyh bayram"), (None, "")],
)
def test_neighborhood_name_normalization(raw: object, expected: str) -> None:
    assert normalize_neighborhood_name(raw) == expected


def test_match_key_removes_spacing_and_punctuation() -> None:
    assert normalize_match_key("B. Mustafa Paşa Mahallesi") == "bmustafapasa"
    assert normalize_match_key("B.MUSTAFAPASA") == "bmustafapasa"


def test_validate_geojson_rejects_non_wgs84_coordinates() -> None:
    document = {
        "type": "FeatureCollection",
        "features": [polygon_feature({"name": "x"})],
    }
    document["features"][0]["geometry"]["coordinates"][0][0] = [4_250_000, 4_600_000]
    with pytest.raises(GeospatialLayerError, match="outside WGS84"):
        validate_geojson(document, layer_name="test", required_properties={"name"})


def test_validate_geojson_rejects_missing_property() -> None:
    document = {"type": "FeatureCollection", "features": [polygon_feature({})]}
    with pytest.raises(GeospatialLayerError, match="missing properties"):
        validate_geojson(document, layer_name="test", required_properties={"name"})


def test_filter_feature_collection_preserves_metadata() -> None:
    collection = {
        "type": "FeatureCollection",
        "name": "damage",
        "features": [
            polygon_feature({"damage": "Destroyed"}, feature_id="one"),
            polygon_feature({"damage": "Damaged"}, feature_id="two"),
        ],
    }
    filtered = filter_feature_collection(
        collection, property_name="damage", accepted_values={"Destroyed"}
    )
    assert filtered["name"] == "damage"
    assert [feature["id"] for feature in filtered["features"]] == ["one"]
    assert len(collection["features"]) == 2
