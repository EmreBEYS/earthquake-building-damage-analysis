import pytest

from earthquake_damage.geospatial_layers import (
    GeospatialLayerError,
    filter_feature_collection,
    load_map_layers,
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
    assert len(layers.neighborhoods["features"]) == 62
    assert len(layers.damage_polygons["features"]) == 3_617
    assert (
        layers.validation["checks"]["copernicus_damage_polygons"]["source_feature_count"] == 3_619
    )
    assert layers.validation["valid"] is True
    assert layers.manifest["official_record_semantics"].startswith("neighborhood aggregates")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("Çöşnük Mahallesi", "cosnuk"), ("  ŞEYH BAYRAM  ", "seyh bayram"), (None, "")],
)
def test_neighborhood_name_normalization(raw: object, expected: str) -> None:
    assert normalize_neighborhood_name(raw) == expected


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
