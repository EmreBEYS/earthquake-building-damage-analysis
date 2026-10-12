# Data sources and provenance

Last reviewed: 2026-10-12. The machine-readable inventory is
[`data/inventory.csv`](../data/inventory.csv). Raw/external files are local and Git-ignored;
small manifests and validation evidence are committed.

## 1. Copernicus EMSR648 AOI05 grading vectors

- Provider: Copernicus Emergency Management Service (CEMS) On-Demand Mapping.
- Product: `EMSR648_AOI05_GRA_PRODUCT_r1_VECTORS_v1_vector.zip`.
- Acquisition: user-supplied original ZIP; authoritative activation page:
  <https://mapping.emergency.copernicus.eu/activations/EMSR648/>.
- Coverage: AOI05 Malatya urban footprint, bbox `38.210286, 38.287227, 38.364463, 38.398576`
  in WGS 84. It intersects parts of Battalgazi and Yeşilyurt; it is not the union of both
  administrative districts.
- CRS: EPSG:4326, evidenced by all included `.prj` files.
- Dates in the package source table: earthquake/OSM reference 2023-02-06; pre-event ESRI World
  Imagery 2021-08-18; post-event Pleiades-1A/1B 2023-02-09; layer metadata 2023-02-10.
- Important interpretation: this is a **2023 damage-reference product**, not a 2022 image or
  2022 building baseline. The referenced commercial image pixels are not included.
- Terms: CEMS information is free, full and open for reproduction, distribution and adaptation,
  subject to terms, limitations and source attribution:
  <https://mapping.emergency.copernicus.eu/terms-and-conditions/> and
  <https://mapping.emergency.copernicus.eu/about/citation-guidelines/>.
- Required attribution: `Copernicus Emergency Management Service (© 2023 European Union),
  [EMSR648] Malatya (AOI05): Grading Map`.
- Local result: 4,322,776-byte ZIP; SHA-256
  `ab56968a7880f22fbf13df94ec51921079e4f7213e05eb1f9cf3596b346bfd59`.
- Validation: archive CRC and path safety; 75 members; 9 complete shapefile sets; matching
  GeoJSON/SHP feature counts; WGS 84 projection evidence. See
  [`data/manifests/EMSR648_AOI05_layers.csv`](../data/manifests/EMSR648_AOI05_layers.csv).

The `builtUpA` layer contains 3,619 polygons/multipolygons: 102 destroyed, 157 damaged, 93
possibly damaged and 3,267 with no visible damage. These labels are remote
damage interpretation, not engineering safety assessments.

## 2. Administrative district reference

- Provider: geoBoundaries API, `gbOpen/TUR/ADM2`; original boundary source is identified by its
  metadata as OpenStreetMap / OSM Boundaries.
- API metadata: <https://www.geoboundaries.org/api/current/gbOpen/TUR/ADM2/>.
- Pinned GeoJSON: commit `9469f09` in the geoBoundaries repository, recorded in
  `configs/datasets.json`.
- Represented year: 2021; canonical type: districts.
- Licence: the Türkiye ADM2 API record states **ODbL 1.0**. Attribution and database share-alike
  obligations apply. Do not relabel this specific source as CC BY 4.0 merely because other
  geoBoundaries products use that licence.
- Local result: 16,115,778 bytes, 973 valid features, SHA-256
  `8e7594ab12d916e3b93f920475a300c364dfb94a0e40bfa6d55f43aff0c7fd97`.
- Selection: stable `shapeID` values select Battalgazi and the Yeşilyurt polygon that intersects
  AOI05. A second same-name Yeşilyurt elsewhere in Türkiye is intentionally excluded.
- Limitation: this is an open reference boundary, not an asserted official municipal or
  neighbourhood dataset. Official bulk municipal boundaries remain pending until a stable
  download and explicit reuse terms can be verified.

Attribution: `© OpenStreetMap contributors, ODbL 1.0; distributed via geoBoundaries`.

## 3. Sentinel-2 Level-2A scene candidates

- Provider: Copernicus Data Space Ecosystem (CDSE).
- Catalogue: <https://stac.dataspace.copernicus.eu/v1/>; collection `sentinel-2-l2a`.
- Official API documentation:
  <https://documentation.dataspace.copernicus.eu/APIs/STAC.html>.
- Terms: Sentinel data are available on a free, full and open basis under the Copernicus
  Sentinel Data Legal Notice; CDSE terms are at
  <https://dataspace.copernicus.eu/terms-and-conditions>.
- Attribution for unmodified scenes: `Copernicus Sentinel data [year]`; for derived pixels:
  `Contains modified Copernicus Sentinel data [year]`.
- Query bbox: EMSR648 AOI05 bbox in WGS 84; collection L2A; reported cloud cover at most 30%.
- Windows: 2022 summer, 2023 immediate post-event, season-matched 2023 summer, and 2026 summer.

Only catalogue metadata was downloaded. No JP2/TIFF imagery assets are in the repository or local
dataset. The validated catalogues contain 44, 9, 46 and 65 records respectively. The first five
catalogue candidates per window are recorded in
[`data/manifests/sentinel2_candidates.csv`](../data/manifests/sentinel2_candidates.csv).

Cloud percentage is product/tile metadata, not proof that AOI05 itself is cloud-free. Before any
scene download, visually inspect AOI coverage, cloud/shadow, snow, seasonal comparability,
processing baseline and duplicate/reprocessed products.

## 4. Deliberately pending or excluded

| Source | State | Reason |
|---|---|---|
| Official Malatya/Battalgazi/Yeşilyurt municipal or neighbourhood boundaries | Pending | No stable official bulk download with explicit reuse terms was verified in this pass. |
| e-Devlet/account-bound records | Excluded | Private or restricted data must not enter this public repository. |
| ESRI World Imagery / Pleiades pixels referenced by CEMS | Excluded | Proprietary imagery is not included in the CEMS vector package and must not be redistributed. |
| Large Sentinel-2 assets | Pending deliberate selection | Catalogue discovery is complete; downloading scenes would be large and requires visual QA first. |
| 2022 building footprint baseline | Pending | EMSR648 does not provide one. It must be created later from a date-controlled, clearly licensed source. |

No unavailable dataset is represented as acquired. No ML-ready processed dataset has been created.
