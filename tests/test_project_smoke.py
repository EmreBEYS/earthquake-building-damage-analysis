from scripts.check_project import inventory_rows, tracked_payloads, validate_config, validate_inventory


def test_dataset_inventory_is_well_formed() -> None:
    rows = inventory_rows()
    assert rows
    assert validate_inventory(rows) == []


def test_dataset_config_is_well_formed() -> None:
    assert validate_config() == []


def test_git_does_not_track_dataset_payloads() -> None:
    assert tracked_payloads() == []
