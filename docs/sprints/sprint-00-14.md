# Sprint 00-14 — Geometry validation and metric spatial features

## Outcome

Sprint 00-14 validates the committed Sprint 00-12 Copernicus damage polygons and reviewed
neighborhood boundaries, computes metric geometry features, assigns polygons to neighborhoods,
and packages the result as GeoPackage and GeoParquet. The calculation CRS is WGS 84 / UTM zone
37N (EPSG:32637), the appropriate metre-based UTM zone for the Malatya AOI.

The pipeline does not transfer official assessment labels to Copernicus polygons. The building
layer retains only its Copernicus damage attributes plus geometry-derived features and matching
audit fields. The neighborhood layer contains boundary identity, geometry metrics, matched
Copernicus polygon count and density; official damage aggregates are intentionally excluded.

## Reproduction

```powershell
uv sync --locked --all-extras
uv run python scripts/12_prepare_spatial_features.py
uv run pytest -q
uv run ruff check .
```

Inputs and thresholds are pinned in `configs/sprint_00_14.json`. The validation report records
source SHA-256 values, input schemas, CRS, bounds, feature counts, duplicate and overlap checks,
containment and matching results, output SHA-256 values, and reopen validation for every format.

## Outputs

`data/processed/sprint_00-14/sprint_00-14.gpkg` contains `buildings` and `neighborhoods` layers.
Equivalent GeoParquet layers are stored as `buildings.parquet` and `neighborhoods.parquet`.
All three files use EPSG:32637. `reports/sprint_00-14/validation_report.json` is the machine-readable
audit record.

## Quality interpretation

The pipeline preserves source geometries and flags issues instead of silently deleting or
repairing them. Current reviewed results include one exact duplicate building-geometry pair,
eight small building-overlap pairs, 59 small neighborhood-boundary overlap pairs, 19 polygons
outside the reviewed neighborhood boundaries and 122 polygons intersecting more than one
boundary. A representative point is used for the primary match; maximum overlap is the explicit
fallback. Density is `matched Copernicus polygon count / neighborhood area in km²`.

Copernicus `builtUpA` polygons are mapped damage objects, not guaranteed cadastral building
footprints. Quality flags and review thresholds are therefore evidence for inspection, not a
claim that every polygon represents exactly one physical building.
