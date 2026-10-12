# Geospatial data dictionary

## Copernicus EMSR648 AOI05

| Layer suffix | Geometry | Role |
|---|---|---|
| `areaOfInterestA` | Polygon | Common comparison/clipping footprint; not a district boundary. |
| `builtUpA` | Polygon/MultiPolygon | Approximate building/building-block footprints with `damage_gra`. |
| `ancillaryCrisisInfoA` | Polygon | Temporary-camp areas. |
| `ancillaryCrisisInfoP` | Point | Blocked-road/interruption observations. |
| `transportationL` | Line/MultiLineString | Roads, railways and airfield lines with damage interpretation. |
| `hydrographyA`, `hydrographyL` | Polygon/line | Water bodies and watercourses. |
| `physiographyL` | Line/MultiLineString | Terrain/physiographic reference lines. |
| `imageFootprintA` | Polygon | Footprints of source imagery; not the image pixels. |

Key `builtUpA` fields:

| Field | Meaning / caution |
|---|---|
| `obj_type` | CEMS asset class, such as residential/non-residential building. |
| `name` | Feature name where available; often blank. |
| `damage_gra` | `Destroyed`, `Damaged`, `Possibly damaged`, or `No visible damage`. Do not treat as a structural safety certificate. |
| `det_method` | Detection method, normally photo-interpretation. |
| `or_src_id` | Original/reference source ID; join conceptually to the package source table. |
| `dmg_src_id` | Damage-observation source ID; package value 2 points to Pleiades-1A/1B dated 2023-02-09. |

Exact feature counts, geometry types and bboxes are generated in
[`data/manifests/EMSR648_AOI05_layers.csv`](../data/manifests/EMSR648_AOI05_layers.csv).

## geoBoundaries Türkiye ADM2

| Field | Meaning |
|---|---|
| `shapeName` | District display name; not globally unique. |
| `shapeID` | Stable ID used by this workflow for deterministic selection. |
| `shapeGroup` | ISO3 group (`TUR`). |
| `shapeType` | Administrative level (`ADM2`). |

Names alone are unsafe for selection because the source contains two records named Yeşilyurt.

## Sentinel-2 catalogue metadata

| Field | Meaning / caution |
|---|---|
| `id` | STAC item/product identifier; reprocessed versions may coexist. |
| `properties.datetime` | Scene acquisition time in UTC. |
| `properties.eo:cloud_cover` | Tile/product cloud percentage, not AOI-specific cloud cover. |
| `properties.grid:code` | MGRS tile identifier. |
| `properties.processing:version` | Processing baseline used to detect/version comparable products. |
| `links[rel=self]` | Authoritative STAC item metadata URL. |
