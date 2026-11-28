# Data sources and provenance

Last reviewed: 2026-10-13. The machine-readable inventory is
[`data/inventory.csv`](../data/inventory.csv). Raw/external files are local and Git-ignored;
small manifests and validation evidence are committed.

The words “validated” and “catalogued” below refer to the historical validation snapshot dated
2026-10-12. They do not mean those Git-ignored payloads exist after cloning. Reacquisition and
checksum verification are mandatory on each new workstation.

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

The validated catalogue snapshots contain 44, 9, 46 and 65 records respectively. The first five
catalogue candidates per window are recorded in
[`data/manifests/sentinel2_candidates.csv`](../data/manifests/sentinel2_candidates.csv). Sprint
00-13 uses the same reviewed dates to acquire real three-band true-colour GeoTIFFs from the
public Earth Search `sentinel-2-l2a` collection. The downloaded files cover MGRS tile 37SDC,
which contains AOI05, and require no account or API key. GeoTIFFs and their local checksum
manifest are ignored; the keyless search plan is committed as
[`data/manifests/sentinel2_temporal_plan.json`](../data/manifests/sentinel2_temporal_plan.json).

Cloud percentage is product/tile metadata, not proof that AOI05 itself is cloud-free. Before any
scene download, visually inspect AOI coverage, cloud/shadow, snow, seasonal comparability,
processing baseline and duplicate/reprocessed products.

Sprint 00-18 additionally reads public Earth Search COG assets B02, B03, B04, B08, B11, B12 and
SCL for exact items `S2A_37SDC_20221231_0_L2A` and `S2B_37SDC_20230224_0_L2A`. Only AOI clips
are stored locally under ignored `data/external/sentinel_2/spectral/`; their source URLs,
retrieval metadata and SHA-256 values are recorded in the local manifest. Derived vector/CSV
outputs use the attribution `Contains modified Copernicus Sentinel data 2022–2023`.

Sprint 00-19 reads the same Earth Search COG assets for `S2B_37SDC_20230224_0_L2A` and the
season-matched `S2C_37SDC_20260305_0_L2A` (5 March 2026, processing baseline 05.12). The first
run used `S2A_37SDC_20261112_1_L2A`; it was rejected because its seasonal difference from
February masked reconstruction change. Clips are stored under ignored
`data/external/sentinel_2/reconstruction/` with a SHA-256 manifest. Derived outputs use
`Contains modified Copernicus Sentinel data 2023–2026`.

### Dated OSM building snapshots (Sprint 00-19)

- Source: Overpass API attic queries (`[date:"…"]`), endpoints `overpass.private.coffee` and
  `overpass-api.de`; licence ODbL 1.0, © OpenStreetMap contributors.
- Timestamps: 2023-02-24T00:00:00Z (60,598 ways) and 2026-07-27T00:00:00Z (57,468 ways).
- Downloaded 25–28 November 2026 as 16 resumable tiles; merged snapshots and their query,
  `osm_base` and SHA-256 sidecars stay under ignored `data/external/reconstruction/osm/`.
- The ohsome `elements/geometry` endpoint used by Sprint 00-18 returned HTTP 403 for every
  extraction request on 25 November 2026.
- Snapshots record mapping state, not a physical survey date.

## 4. Deliberately pending or excluded

| Source | State | Reason |
|---|---|---|
| Official Malatya/Battalgazi/Yeşilyurt municipal or neighbourhood boundaries | Pending | No stable official bulk download with explicit reuse terms was verified in this pass. |
| e-Devlet/account-bound records | Excluded | Private or restricted data must not enter this public repository. |
| ESRI World Imagery / Pleiades pixels referenced by CEMS | Excluded | Proprietary imagery is not included in the CEMS vector package and must not be redistributed. |
| Full-tile Sentinel-2 spectral assets | Excluded from Git | Sprint 00-18 streams and stores only ignored AOI clips; full rasters remain external. |
| 2022 building footprint baseline | Pending | EMSR648 does not provide one. It must be created later from a date-controlled, clearly licensed source. |

## 5. Acquisition candidates not yet downloaded

| Source | Intended role | Gate before acquisition/use |
|---|---|---|
| USGS ComCat FDSN event API | Reproducible event catalogue for the February 2023 sequence | Commit exact spatial/time/magnitude query, preserve response bytes and checksum, and reconcile preferred origin/magnitude with AFAD. |
| OpenStreetMap historical extract | Pre-event building-footprint candidate | Obtain a dated snapshot no later than 2023-02-05; current OSM is not a pre-event baseline. Preserve ODbL attribution/share-alike obligations. |
| WorldPop Türkiye 2021 | Optional population-exposure covariate | Verify the product README, CC BY 4.0 terms, CRS, nodata, resolution and checksum before clipping. It is not a damage label. |
| AFAD 6 February reference | Authoritative Turkish agency event metadata | Use as a documented reference only until stable structured access and explicit redistribution terms are verified. |

The source pages reviewed for this plan are the USGS FDSN API and USGS data-licensing guidance,
the OpenStreetMap copyright page, the WorldPop Türkiye product README, and the AFAD 6 February
information page. Source URLs and current disposition are recorded in the inventory.

No unavailable dataset is represented as acquired. No ML-ready processed dataset has been created.
