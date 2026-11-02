from scripts.check_project import (
    ALLOWED_TRACKED_DATA_PAYLOADS,
    inventory_rows,
    tracked_payloads,
    validate_config,
    validate_inventory,
)


def test_dataset_inventory_is_well_formed() -> None:
    rows = inventory_rows()
    assert rows
    assert validate_inventory(rows) == []


def test_dataset_config_is_well_formed() -> None:
    assert validate_config() == []


def test_git_tracks_only_approved_dataset_payloads() -> None:
    assert ALLOWED_TRACKED_DATA_PAYLOADS == {
        "data/processed/sprint_00-14/buildings.parquet",
        "data/processed/sprint_00-14/neighborhoods.parquet",
        "data/processed/sprint_00-14/sprint_00-14.gpkg",
    }
    assert tracked_payloads() == []

