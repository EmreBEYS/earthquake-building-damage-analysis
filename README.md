# Earthquake Building Damage Analysis

Data-driven analysis of how structural and seismic characteristics influence
post-earthquake building damage levels.

## Overview

This project investigates relationships between building attributes, ground
motion indicators, and observed post-earthquake damage. Its first goal is an
explainable and reproducible analysis; predictive models are used as supporting
tools rather than as substitutes for engineering judgment.

The current phase is limited to the **Malatya AOI05 data foundation**. It preserves and
validates source data, inventories licences and coverage, and records 2022/2023/2026 imagery
candidates. No machine-learning model is implemented in this phase.

## Current Dataset Status

- Copernicus EMSR648 AOI05 2023 grading vectors: locally preserved and validated; raw bytes
  remain Git-ignored.
- Türkiye ADM2 boundaries: pinned geoBoundaries/OSM-derived source downloaded and validated;
  Battalgazi and the Malatya Yeşilyurt records are reproducibly selected after validation.
- Sentinel-2 L2A: 2022 summer, 2023 post-event, 2023 summer and 2026 summer STAC catalogue
  metadata collected; imagery assets are not downloaded or committed.
- Official municipal/neighbourhood boundaries: pending a stable official bulk download with
  explicit reuse terms.
- Private e-Devlet data and proprietary VHR imagery: explicitly excluded.

See [`data/inventory.csv`](data/inventory.csv), [`data/validation_report.json`](data/validation_report.json)
and [`docs/data-sources.md`](docs/data-sources.md) for evidence and limitations.

## Research Questions

- Which structural and seismic variables are most strongly associated with damage severity?
- How well can damage levels be estimated from the available pre-event and event data?
- Which models offer the best balance between predictive performance and interpretability?
- How stable are the findings across locations, building types, and validation splits?

## Planned Workflow

1. Define the study scope and select a documented data source.
2. Create a data dictionary and audit missing values, labels, and class balance.
3. Clean and validate the data without modifying the original raw files.
4. Perform exploratory and geospatial analysis where location data permits it.
5. Build transparent baselines, followed by stronger machine-learning models.
6. Evaluate with class-aware metrics and inspect error patterns.
7. Report limitations, uncertainty, and engineering implications.

## Repository Structure

```text
earthquake-building-damage-analysis/
├── configs/               # Experiment and data-processing configuration
├── data/
│   ├── external/          # Third-party reference data (not committed)
│   ├── interim/           # Intermediate datasets (not committed)
│   ├── processed/         # Analysis-ready datasets (not committed)
│   └── raw/               # Immutable source data (not committed)
├── docs/                  # Research notes, data dictionary, and methodology
├── models/                # Trained model artifacts (not committed)
├── notebooks/             # Numbered exploratory notebooks
├── reports/
│   └── figures/           # Generated figures for reports
├── src/earthquake_damage/
│   ├── data/              # Ingestion and validation
│   ├── evaluation/        # Metrics and error analysis
│   ├── features/          # Feature engineering
│   ├── modeling/          # Training and inference
│   └── visualization/     # Reusable plotting functions
├── scripts/               # Immutable acquisition, validation, and post-validation extraction
└── tests/                 # Automated tests
```

## Getting Started

Prerequisites: Python 3.11 or later.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Place source datasets under `data/raw/` and document their origin and license in
`docs/data-sources.md`. Do not commit datasets containing personal, sensitive,
restricted, or third-party licensed information.

Run the initial checks with:

```bash
pytest
ruff check .
```

Dataset commands are documented in [`scripts/README.md`](scripts/README.md). They use only the
Python standard library and can be run before installing the analytical dependencies.

## Evaluation Principles

Damage severity is normally imbalanced and ordinal. Accuracy alone is therefore
not sufficient. Candidate metrics include macro F1, per-class precision and
recall, a confusion matrix, and ordinal-aware error measures. Validation must
avoid leakage between observations that belong to the same building, site, or
event when those groupings are present.

## Responsible Use

This repository is intended for academic research and decision support. Results
must not be used as a standalone structural safety assessment. Any operational
use requires review by qualified civil/earthquake engineering professionals and
validation against the target region and data collection process.

## License

MIT is recommended for the source code; see [LICENSE](LICENSE). Dataset, map,
imagery, and pretrained-model licenses remain separate and must be documented
before redistribution.

