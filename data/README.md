# Dataset layout and handling rules

This repository keeps **metadata and reproducible acquisition/validation code** in Git,
but not large or third-party data files.

```text
data/
├── raw/          # immutable first-party/source deliveries; never edited in place
├── external/     # immutable third-party reference data and catalogue responses
├── interim/      # reproducible extracts/reprojections made from validated inputs
├── processed/    # analysis-ready products; not created in this phase
├── manifests/    # small, reviewable metadata committed to Git
├── inventory.csv # one row per source or deliberately excluded/pending source
├── validation_report.json # committed historical evidence; not proof of clean-clone availability
└── local-validation-report.json # optional ignored report for the current machine
```

## Non-negotiable rules

1. Raw and external files are immutable. A changed checksum is a new source version.
2. Validate archive safety, checksums, JSON structure, feature counts and CRS evidence before
   any extraction or transformation.
3. Never commit satellite scenes, raw vector packages, credentials, private e-Devlet exports,
   personal data, or proprietary imagery.
4. A public web page is not sufficient proof of redistribution rights. Record the specific
   dataset licence/terms and attribution.
5. `interim/` and `processed/` must be reproducible from scripts; neither is a substitute for
   the preserved original source.

## Reproduce the local dataset

The uploaded Copernicus ZIP is intentionally not fetched by the public acquisition command.
Copy it from a trusted local location while preserving its bytes:

```bash
python scripts/acquire_data.py copy-cems --source /path/to/EMSR648_AOI05_GRA_PRODUCT_r1_VECTORS_v1_vector.zip
python scripts/acquire_data.py download-boundaries
python scripts/acquire_data.py query-sentinel
python scripts/validate_data.py
```

Only after validation passes, create the AOI-relevant district extract:

```bash
python scripts/prepare_aoi_boundaries.py
```

The Sentinel command stores catalogue metadata only. It does not download imagery assets.
Scene selection must be reviewed for season, cloud/shadow, coverage and product baseline before
any later imagery download.

## Sprint 00-12 dashboard exception

`data/dashboard/sprint_00-12/` contains compact, derived display layers so a clean clone can
render the research map. These are not raw source archives. Their provenance, attribution,
feature counts, CRS and exclusions are recorded in the adjacent manifest and validation report.
Official damage values in the neighborhood layer are aggregates only and must not be interpreted
as building coordinates. The adjacent coverage CSV retains all 80 exact-match neighborhoods,
while the unmatched CSV reports the remaining 2,737 records without assigning geometry.

Inventory status is deliberately separate from repository availability:

- `validated_local_only` and `catalogued_local_only` mean the committed checksum/evidence came
  from a prior local workspace; the payload is not in Git.
- `planned` and `pending_verified_download` mean no usable local dataset is claimed.
- `excluded_private` and `excluded_proprietary` are guardrails, not acquisition tasks.

Run `python scripts/check_project.py` at any time to check the layout, inventory metadata and
the invariant that Git does not track data payloads. This smoke check does not require datasets
or network access.

