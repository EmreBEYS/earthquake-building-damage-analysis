# Sprint 00-13 — Sentinel-2 temporal GeoTIFF acquisition

## Outcome

Sprint 00-13 defines a reproducible, keyless way to acquire actual satellite pixels for AOI05.
It does not use browser screenshots or proprietary imagery referenced by CEMS. The workflow
searches the public Earth Search STAC catalogue and downloads the `visual` Sentinel-2 Level-2A
Cloud-Optimized GeoTIFF for MGRS tile 37SDC, which contains AOI05.

Satellite pixels are a separate evidence source. They are not official building assessments,
do not geolocate official records to buildings, and are not treated as building-level damage
labels.

## Reviewed temporal set

| Label | Acquisition | Role | Catalogue cloud |
|---|---|---|---:|
| `pre_event_2022_summer` | 2022-08-05 | seasonal pre-event baseline | 0.00% |
| `post_event_2023_immediate` | 2023-02-26 | post-event observation | 1.24% |
| `post_event_2023_summer` | 2023-09-19 | season-matched post-event observation | 0.00% |

At download time the script searches the date and AOI, restricts results to 37SDC and selects
the lowest-cloud item that provides a `visual` asset. Catalogue cloud percentage describes the
whole product/tile, not AOI-specific cloud or shadow. Visual QA remains required before
scientific use.

## Raster contract

- coverage: full Sentinel-2 MGRS tile 37SDC containing EMSR648 AOI05;
- output CRS: EPSG:32637;
- raster dimensions: 10,980 × 10,980 pixels;
- pixel size: 10 m;
- bands: red, green and blue true-colour visualization;
- format: public Cloud-Optimized GeoTIFF, not a screenshot;
- local destination: `data/external/sentinel_2/geotiff/` (Git-ignored); and
- attribution: `Contains modified Copernicus Sentinel data 2022–2023`.

Each catalogue search has a deterministic SHA-256 in
`data/manifests/sentinel2_temporal_plan.json`. Download validation checks TIFF signature, band
count, EPSG evidence, pixel scale, byte size and file SHA-256. The local acquisition manifest is
kept beside the ignored GeoTIFFs.

The `visual` asset is suitable for robust visual before/after review. A later quantitative
spectral analysis should acquire reflectance assets such as red and near-infrared separately
and crop/reproject them with a geospatial raster library; the RGB visualization must not be
misrepresented as four-band reflectance data.

## Reproduction

No Copernicus OAuth client, API key or AWS account is required:

```powershell
python scripts/11_acquire_sentinel2_temporal.py plan
python scripts/11_acquire_sentinel2_temporal.py download
python scripts/11_acquire_sentinel2_temporal.py validate
```

One scene can be selected with `--scene`, for example:

```powershell
python scripts/11_acquire_sentinel2_temporal.py download `
  --scene pre_event_2022_summer
```

Existing GeoTIFFs are reused rather than silently overwritten. Full Sentinel-2 tiles can be
large, so imagery stays out of Git.

## Interface

The Streamlit `Uydu · Zaman Serisi` page displays the three reviewed dates, roles, catalogue
cloud metadata, raster contract and whether each ignored local GeoTIFF is present. It does not
render a JPEG screenshot as analysis data and does not present satellite pixels as an official
safety assessment.
