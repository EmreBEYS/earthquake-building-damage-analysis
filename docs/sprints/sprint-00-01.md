# Sprint 00-01 — Project and dataset infrastructure

Status: implementation complete; external data handoff remains.

## Goal

Provide a reproducible Python repository and an auditable, licence-aware acquisition plan for
open geographic and building-damage data related to the 6 February 2023 earthquakes, with the
initial analysis footprint limited to Copernicus EMSR648 Malatya AOI05.

## Delivered

- `src/` package layout, numbered notebooks, tests, scripts, configs, reports and model folders.
- Immutable `raw`/`external`, reproducible `interim`/`processed`, and Git-ignore guardrails.
- Machine-readable source inventory with provenance, licence/terms, redistribution decision,
  temporal/spatial scope, local target and checksum where a payload was previously validated.
- Standard-library acquisition and validation scripts that refuse to overwrite changed inputs.
- Offline project smoke checks plus pytest, Ruff and GitHub Actions automation.
- Python 3.11 selection and a cross-platform `uv.lock` for repeatable dependency resolution.
- CEMS, geoBoundaries and Sentinel-2 provenance; planned USGS, historical OSM and WorldPop
  inputs; explicit exclusion of private e-Devlet data and proprietary VHR image pixels.

## Definition of done

- `uv sync --locked --all-extras` succeeds from a clean clone.
- `uv run ruff check .`, `uv run pytest -q` and
  `uv run python scripts/check_project.py` pass without datasets or network access.
- No data payload is tracked under `data/raw`, `data/external`, `data/interim` or
  `data/processed`.
- Every inventory row has a source disposition and licence/terms decision.
- Documentation distinguishes historical validation evidence from files available in a clone.

## External-access handoff

The repository does not contain or fabricate real datasets. Before analysis:

1. Obtain the exact EMSR648 AOI05 vector ZIP from a trusted source and run `copy-cems`; its bytes
   must match the recorded SHA-256 checksum.
2. Run `download-boundaries`; if the pinned file is no longer served, review and version a new
   source instead of changing the checksum in place.
3. Re-query Sentinel-2 catalogue metadata. Select imagery only after visual cloud/shadow, snow,
   coverage and processing-baseline review; large image assets require a deliberate later step.
4. Define and review the USGS query, then preserve its exact response. Cross-check event fields
   against AFAD because preferred origins and magnitudes can differ by agency or revision.
5. Source a dated OSM extract at or before 2023-02-05 if a pre-event building baseline is needed.
6. Verify official municipal/neighbourhood reuse terms before adding any such boundaries.

No processed or ML-ready dataset is claimed at Sprint 00-01 completion.
