import runpy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = runpy.run_path(str(ROOT / "scripts" / "11_acquire_sentinel2_temporal.py"))


def test_temporal_plan_is_keyless_and_contains_three_windows() -> None:
    config = SCRIPT["load_config"]()
    plan = SCRIPT["build_plan"](config)
    assert plan["sprint"] == "00-13"
    assert plan["authentication"] == "not_required"
    assert [scene["label"] for scene in plan["scenes"]] == [
        "pre_event_2022_summer",
        "post_event_2023_immediate",
        "post_event_2023_summer",
    ]
    assert plan["output"]["bands"] == ["red", "green", "blue"]
    assert plan["output"]["scope"] == "full_mgrs_tile"
    assert (plan["output"]["width"], plan["output"]["height"]) == (10980, 10980)
    assert len({scene["search_sha256"] for scene in plan["scenes"]}) == 3
    assert all(len(scene["search_sha256"]) == 64 for scene in plan["scenes"])
    assert "does not geolocate official records to buildings" in plan["interpretation"]


def test_search_has_fixed_aoi_date_collection_and_no_credentials() -> None:
    config = SCRIPT["load_config"]()
    scene = config["scenes"][0]
    parameters = SCRIPT["search_parameters"](config, scene)
    assert parameters == {
        "collections": "sentinel-2-l2a",
        "bbox": "38.210286,38.287227,38.364463,38.398576",
        "datetime": "2022-08-05T00:00:00Z/2022-08-05T23:59:59Z",
        "limit": "100",
    }
    url = SCRIPT["search_url"](config, scene)
    assert url.startswith("https://earth-search.aws.element84.com/v1/search?")
    assert "client" not in url.lower()
    assert "token" not in url.lower()


def test_select_item_requires_target_mgrs_and_visual_asset() -> None:
    config = SCRIPT["load_config"]()
    wrong_tile = {
        "id": "wrong",
        "properties": {"mgrs:utm_zone": 36, "eo:cloud_cover": 0},
        "assets": {"visual": {"href": "https://example.test/wrong.tif"}},
    }
    cloudy = {
        "id": "S2_37SDC_cloudy",
        "properties": {"eo:cloud_cover": 20},
        "assets": {"visual": {"href": "https://example.test/cloudy.tif"}},
    }
    clear = {
        "id": "S2_37SDC_clear",
        "properties": {"eo:cloud_cover": 1},
        "assets": {"visual": {"href": "https://example.test/clear.tif"}},
    }
    selected = SCRIPT["select_item"](config, {"features": [wrong_tile, cloudy, clear]})
    assert selected["id"] == "S2_37SDC_clear"


def test_unknown_scene_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown scene labels"):
        SCRIPT["selected_scenes"](SCRIPT["load_config"](), ["missing"])
