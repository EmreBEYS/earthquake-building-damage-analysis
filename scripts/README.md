# Data acquisition and validation scripts

All scripts are intentionally standard-library Python. They separate immutable acquisition,
read-only validation and post-validation extraction.

## `acquire_data.py`

- `copy-cems --source PATH`: checksum-verifies and copies the trusted uploaded ZIP. It refuses
  to overwrite a different existing raw file.
- `download-boundaries`: downloads the commit-pinned Türkiye ADM2 GeoJSON and verifies SHA-256.
- `query-sentinel`: queries the official CDSE STAC endpoint and stores compact scene metadata;
  it never downloads imagery assets and refuses to overwrite changed catalogue snapshots.

Network URLs, expected checksums, AOI bbox and time windows live in
[`configs/datasets.json`](../configs/datasets.json).

## `validate_data.py`

Validation is read-only for raw/external inputs. It checks:

- inventory paths and recorded SHA-256 values;
- ZIP CRC and path traversal safety;
- complete SHP/SHX/DBF/PRJ component sets;
- shapefile header integrity and SHP/GeoJSON feature-count agreement;
- GeoJSON FeatureCollection/geometry structure, counts and bboxes;
- WGS 84 CRS evidence in the CEMS projection files.

It writes small, reviewable evidence to `data/validation_report.json` and `data/manifests/`.

The committed report is historical evidence from the workspace where the ignored payloads were
available. A clean clone should not run validation until the selected payloads have been acquired;
missing files are a failure, not silently treated as valid.

## `check_project.py`

This offline smoke check validates the expected project layout, config shape, inventory columns,
status vocabulary, URLs/checksums and the rule that Git tracks no dataset payloads. It does not
claim that ignored datasets exist:

```bash
python scripts/check_project.py
```

## `prepare_aoi_boundaries.py`

This script will not run unless the boundary source has a passing validation report. It selects
the configured Battalgazi and Malatya Yeşilyurt `shapeID` values into an ignored interim GeoJSON.
It does not modify the downloaded Türkiye source.

## Order of operations

```bash
python scripts/acquire_data.py copy-cems --source /trusted/path/file.zip
python scripts/acquire_data.py download-boundaries
python scripts/acquire_data.py query-sentinel
python scripts/validate_data.py
python scripts/prepare_aoi_boundaries.py
```

When a source changes, create a new versioned destination and update the inventory/checksum after
review. Do not bypass the overwrite refusal.
