# Sprint 00-12 — Geospatial layer integration

## Outcome

Sprint 00-12 adds version-controlled, audited map layers and an interactive Streamlit map.
The implementation uses two deliberately separate evidence units:

- Copernicus EMSR648 AOI05 mapped damage polygons; and
- official assessment **neighborhood aggregates** joined to neighborhood boundaries.

Official assessment rows are not assigned coordinates and are not claimed to identify a
specific physical building. The dashboard does not infer a building-level match between an
official row and a Copernicus polygon.

## Committed display layers

`data/dashboard/sprint_00-12/` contains compact WGS84 GeoJSON files that can be loaded by a
clean clone:

| Layer | Display features | Source features | Notes |
|---|---:|---:|---|
| AOI05 high-coverage neighborhoods | 62 | 62 | OSM relation ID + normalized-name match; 26,692 official rows aggregated |
| Exact-match neighborhood coverage | 80 | 80 | 43,826 records; high/medium/low AOI coverage retained |
| Boundary-unmatched official aggregates | 7 groups | 2,737 records | Table only; no geometry is invented |
| Copernicus damage polygons | 3,617 | 3,619 | Two source geometries became empty/non-polygonal during validity repair and are excluded |

The accompanying manifest and validation report record feature counts, geometry types, WGS84
bounds, name/ID match counts, damage-class counts, exclusions and the explicit absence of a
building-geolocation claim.

## Validation contract

The preparation command:

1. refuses to guess a missing CRS;
2. reprojects both sources to EPSG:4326;
3. checks for null, empty and invalid geometry;
4. repairs polygon geometry conservatively and reports exclusions;
5. joins neighborhoods by exact OSM relation ID;
6. independently requires normalized Turkish names to agree;
7. verifies all 80 exact-name matches and records which 62 currently have committed display geometry;
8. reproduces each aggregate from `person_01`, `person_02` and `person_03`; and
9. writes only neighborhood or unmatched-name aggregates for official records.

Runtime loading repeats structural GeoJSON, coordinate-range, required-property, geometry-type
and duplicate-ID checks before Streamlit renders a layer.

## Reproduction

Install the geospatial analysis dependencies, place the validated Copernicus source package in
the documented raw-data location, then run:

```powershell
uv sync --locked --all-extras
uv run python scripts/10_acquire_osm_neighborhoods.py
uv run python scripts/10_prepare_geospatial_layers.py `
  --neighborhoods data/external/osm/aoi05_exact_match_neighborhoods.geojson `
  --copernicus data/raw/copernicus_emergency/EMSR648_AOI05_GRA_PRODUCT_r1_VECTORS_v1/original/EMSR648_AOI05_GRA_PRODUCT_builtUpA_r1_v1.json
uv run pytest
uv run streamlit run dashboard.py
```

The OSM acquisition command performs two rate-limited lookups for the relation IDs already
committed in the Sprint 00-10 match report. OSM geometries may evolve; regenerate and review the
validation diff rather than assuming a later response is byte-identical.

## Interface

The `Harita · Katmanlar` page supports:

- independent neighborhood-aggregate and Copernicus layer visibility;
- `person_01`, `person_02` and `person_03` source-group filtering;
- high/medium/low AOI coverage filtering;
- minimum official-record filtering;
- neighborhood selection;
- Copernicus damage-class filtering;
- a complete 80-neighborhood coverage table and a separate 2,737-record unmatched table;
- separate hover semantics for official aggregates and Copernicus observations; and
- visible audit counts for valid and excluded geometries.

Satellite GeoTIFF acquisition and temporal before/after imagery are intentionally deferred to
Sprint 00-13.

