# Earthquake Building Damage Analysis

Data-driven analysis of how structural, geographical, and seismic characteristics influence post-earthquake building damage levels.

## Overview

This project investigates relationships between building attributes, ground motion indicators, geographical characteristics, and observed post-earthquake damage.

The primary objective is to develop an **explainable, reproducible, and geographically informed earthquake damage analysis framework**, with a particular focus on Malatya, Türkiye, following the February 6, 2023 earthquakes.

Predictive machine-learning models are intended to support scientific analysis rather than replace engineering judgment.

The research combines two complementary components:

1. **Building Damage Classification:** Analysis and prediction of post-earthquake building damage severity using validated datasets and appropriate machine-learning methods.
2. **Spatial and Temporal Analysis:** Investigation of changes in the built environment across Malatya, particularly Yeşilyurt and Battalgazi, using available pre-event, post-event, and 2026 geographical data.

The current development stage has completed the initial official damage-record extraction and integration pipeline. Machine-learning training and the interactive analysis interface are planned for subsequent sprints.

## Current Dataset Status

### 1. Official Building Damage Records

Official building damage assessment records originating from the Republic of Türkiye Ministry of Environment, Urbanization and Climate Change have been processed from PDF documents.

The extraction workflow uses Python, PyMuPDF, and pandas to convert tabular damage assessment records into a structured dataset.

**Dataset summary — Sprint 00-09**

| Metric | Result |
|---|---:|
| Total PDF documents | 87 |
| Successfully processed PDFs | 87 |
| Failed PDFs | 0 |
| Extracted raw table rows | 55,435 |
| Accepted damage records | 46,563 |
| Records passing automated baseline checks | 46,563 |
| Damage categories | 6 |
| Potential duplicates detected by current rules | 0 |
| Missing neighbourhood values detected | 0 |
| Invalid assessment codes detected | 0 |
| Conflicting damage classifications detected | 0 |

The dataset was assembled from three independently processed groups of source documents.

| Dataset group | Accepted records |
|---|---:|
| Person 01 | 15,413 |
| Person 02 | 16,420 |
| Person 03 | 14,730 |
| **Total** | **46,563** |

#### Damage Class Distribution

| Damage classification | Records |
|---|---:|
| No Damage (Hasarsız) | 10,131 |
| Slight Damage (Az Hasarlı) | 20,706 |
| Moderate Damage (Orta Hasarlı) | 1,593 |
| Heavy Damage (Ağır Hasarlı) | 12,276 |
| Urgent Demolition (Acil Yıktırılacak) | 955 |
| Collapsed (Yıkık) | 902 |
| **Total** | **46,563** |

The dataset is class-imbalanced. Consequently, future classification experiments will prioritize class-aware evaluation metrics.

**Data quality limitations:** Passing automated validation does not guarantee that each observation represents a unique physical building or that geographical information is independently verified. The current neighbourhood attribution and duplicate-detection rules require additional review. Assessment statuses excluded during extraction must also be considered when interpreting dataset coverage.

The accepted records should not be interpreted as a statistically representative sample of all buildings in Malatya without further coverage assessment.

### 2. Copernicus EMSR648 — AOI05

Copernicus EMSR648 AOI05 2023 grading vectors were validated in a prior local workspace.

Validation evidence and checksums are recorded in the repository, while source files are not redistributed.

This dataset is intended to support spatial damage analysis and geographical feature development.

### 3. Geographical and Remote Sensing Data

- A pinned Türkiye ADM2 geoBoundaries/OSM-derived file was previously validated. A clean clone must reacquire it and verify the recorded checksum.
- Sentinel-2 L2A catalogue snapshots were previously collected for 2022, 2023, and 2026. Checksums and a small candidate manifest are committed; snapshots and imagery are not distributed.
- USGS ComCat events, dated pre-event OSM building snapshots, and WorldPop exposure information remain documented acquisition candidates.
- Official neighbourhood boundaries require a stable, documented source with appropriate reuse permissions.
- Private e-Devlet records and proprietary very-high-resolution imagery are explicitly excluded.

See `data/inventory.csv`, `data/validation_report.json`, and `docs/data-sources.md` for source documentation and limitations.

## Research Questions

- Which structural, geographical, and seismic characteristics are most strongly associated with building damage severity?
- How accurately can damage severity be estimated using information available independently of the official damage assessment?
- How do damage distributions differ across neighbourhoods in Yeşilyurt and Battalgazi?
- What changes in the built environment can be identified between pre-event, post-event, and 2026 observations?
- Which machine-learning methods provide the best balance between performance, interpretability, and reliability?
- How robust are model results across different spatial validation strategies?

## Methodology

The project follows a reproducible analytical workflow.

1. Identify and document official and open geographical data sources.
2. Preserve raw source documents without modification.
3. Extract structured data from official damage assessment PDFs.
4. Normalize damage labels and geographical identifiers.
5. Audit missing fields, duplicated observations, invalid values, and class imbalance.
6. Investigate geographical linkage opportunities and independent predictive features.
7. Conduct exploratory data analysis and spatial analysis.
8. Train transparent baseline models followed by stronger machine-learning alternatives.
9. Evaluate classification performance, spatial generalization, and uncertainty.
10. Develop an interactive analysis and visualization interface.
11. Document results, limitations, and reproducibility requirements.

## Development Progress

| Sprint | Scope | Status |
|---|---|---|
| 00-01 | Project foundation and dataset infrastructure | Completed |
| 00-02 | Initial data preparation and preprocessing | Completed |
| 00-08 | Official PDF extraction and dataset construction | Completed |
| 00-09 | Multi-source validation and dataset integration | Completed |
| 00-10 | Exploratory analysis and machine-learning training | Planned |
| 00-11 | Interactive dashboard and spatial visualization | Planned |

### Sprint 00-08 — Official Damage Dataset Extraction

Implemented a structured PDF extraction workflow.

Main script:

`08_build_official_dataset.py`

Implemented capabilities:

- Recursive PDF discovery
- Table extraction using PyMuPDF
- Assessment-code validation
- Standardized damage-label mapping
- Source PDF and page traceability
- Intermediate CSV export
- Per-document extraction quality reporting
- File-based processing cache
- Preservation of original source documents

### Sprint 00-09 — Dataset Validation and Integration

Implemented a consolidated validation and integration pipeline.

Main script:

`09_validate_and_merge.py`

Implemented capabilities:

- Consolidation of three source-document groups
- Neighbourhood name normalization
- Assessment-code format validation
- Damage-category consistency checks
- Potential duplicate identification
- Missing-data identification
- Per-group dataset exports
- Quality-control summaries
- Integrated analysis dataset generation

**Sprint result:** 46,563 accepted records from 87 PDF documents successfully passed the implemented baseline checks.

The integration pipeline preserves source traceability and generates separate reports for records requiring additional inspection.


## Sprint 00-10 — Machine Learning and Spatial Analysis

This sprint establishes reproducible exploratory baselines for
post-earthquake damage analysis in Malatya, Türkiye.

The study uses three complementary approaches:

- V1: Copernicus EMSR648 AOI05 damage classification.
- V2: Six-class official damage-record classification.
- V3: Historical OpenStreetMap features and neighborhood-level
  spatial analysis.

These experiments use different targets and evaluation units.
Their performance metrics must not be compared directly.

### Dataset Overview

| Dataset | Records | Purpose |
|---|---:|---|
| Official damage records | 46,563 | Six-class damage analysis |
| Copernicus EMSR648 AOI05 | 3,619 | Mapped damage polygons |
| Historical OSM buildings | 3,545 | Pre-event building geometry |
| Neighborhood geometries | 91 | Spatial reference |
| Exactly matched neighborhoods | 80 | Official-OSM linkage |
| High-coverage neighborhoods | 62 | Exploratory V3 analysis |

Historical OSM building data represents the mapping state
on February 5, 2023, before the February 6 earthquakes.

The OSM dataset is incomplete and should not be interpreted
as a complete building inventory.

### V1 — Copernicus Damage Classification

Three geometric features were evaluated:

- Polygon area
- Polygon perimeter
- Shape index

Models included Dummy, Logistic Regression, and Random Forest.

Spatial holdout results:

| Model | Accuracy | Macro F1 |
|---|---:|---:|
| Random Forest | 0.9177 | 0.2395 |

The model failed to recover the minority damage categories
reliably and is unsuitable for operational damage prediction.

### V2 — Official Damage Classification

The official dataset contains 46,563 records and six classes:

- Hasarsiz
- Az hasarli
- Orta hasarli
- Agir hasarli
- Acil yiktirilacak
- Yikik

Only neighborhood information was used as a baseline predictor.

| Model | Accuracy | Macro F1 |
|---|---:|---:|
| Dummy | 0.4447 | 0.1026 |
| Balanced Random Forest | 0.3066 | 0.2517 |
| Oversampled Random Forest | 0.3137 | 0.2569 |

These results use a stratified random split. They do not
demonstrate generalization to unseen geographic areas.

### V3 — Historical OSM and Neighborhood Analysis

Historical building footprints were retrieved from OpenStreetMap
for February 5, 2023.

Preparation results:

- 3,629 downloaded OSM building geometries
- 3,545 intersecting the AOI
- 0 invalid geometries
- 47 buildings with floor-count information
- 0 buildings with construction-date information

Geometric matching with Copernicus revealed substantial
differences in mapping units.

- 3,501 intersecting candidate geometry pairs
- 334 single-candidate pairs
- 16 single-candidate pairs with IoU >= 0.5
- 8 high-overlap manual-review candidates

Damage labels were not automatically transferred between
Copernicus polygons and OSM buildings.

### Neighborhood-Level V3 Results

Of the 91 neighborhood geometries:

- 80 matched official neighborhood names exactly and uniquely
- 62 were classified as high AOI coverage
- 26,692 official records belonged to these 62 neighborhoods
- 2,124 historical OSM buildings were assigned to them

The primary outcome was the share of official assessment
records classified as severely damaged, urgently requiring
demolition, or destroyed.

Spearman correlation between mapped OSM building count and
the severe-damage share:

- All 62 neighborhoods: rho = -0.2934
- Neighborhoods with at least 10 mapped buildings:
  rho = -0.5274 (34 neighborhoods)

These are exploratory associations, not causal findings.
Mapping completeness, spatial dependence, and sample selection
may affect the correlations.

### V3 — Spatial Baseline Evaluation

A five-group spatial cross-validation experiment compared
DummyRegressor and Ridge regression.

| Model | MAE | Weighted MAE |
|---|---:|---:|
| DummyRegressor | 0.1785 | 0.1442 |
| Ridge Regression | 0.1784 | 0.1416 |

Ridge did not provide a meaningful improvement over the
mean-prediction baseline.

MAE measures errors in neighborhood-level severe-damage
proportions, not individual-building classification accuracy.

### Reproducibility and Data Limitations

- The study uses a fixed Malatya AOI of approximately 86.68 km².
- Historical OSM data was queried for February 5, 2023.
- Public dataset provenance, licensing, and processing
  assumptions must be preserved.
- Raw source datasets may require separate retrieval.
- Official records are not automatically linked to individual
  OSM building geometries.
- Neighborhood names require cautious normalization and
  geographic verification.
- Full neighborhood-boundary coverage and assessment-record
  comparability require further verification.
- V1, V2, and V3 are research baselines, not engineering
  safety assessments.

Detailed results are stored in `reports/sprint_00-10/`.

## Next Sprint — 00-11

Sprint 00-11 will focus on a Streamlit research dashboard
featuring:

- Official damage-class distributions
- Neighborhood-level spatial visualizations
- Historical OSM building coverage
- V1, V2, and V3 experiment summaries
- Dataset provenance and limitations

The dashboard will display validated analyses rather than
unsupported building-level damage predictions.


### Sprint 00-11 — Interactive Analysis Interface

Planned capabilities:

- Dataset overview and statistical summaries
- Damage category distribution charts
- Neighbourhood-level comparisons
- Geospatial damage visualization
- Trained model evaluation results
- Interactive feature exploration
- Model inference where supported by validated input features

The initial technology candidates include Streamlit, GeoPandas, Folium, and Plotly.

## Repository Structure

```text
earthquake-building-damage-analysis/
├── configs/
├── data/
│   ├── external/
│   ├── final/                 # Integrated datasets (not committed)
│   ├── interim/               # Extracted intermediate records
│   ├── processed/             # Validated per-group datasets
│   └── raw/                   # Original source data
├── docs/
│   ├── sprints/
│   └── data-sources.md
├── models/
├── notebooks/
├── reports/
│   ├── figures/
│   └── sprint_00-09/
├── scripts/
│   ├── 08_build_official_dataset.py
│   ├── 09_validate_and_merge.py
│   └── README.md
├── src/earthquake_damage/
│   ├── data/
│   ├── evaluation/
│   ├── features/
│   ├── modeling/
│   └── visualization/
└── tests/
```

The structure above describes the current and intended locations of the main project components. Some planned directories may not yet contain implementation files.

## Getting Started

### Requirements

- Python 3.11
- [uv](https://docs.astral.sh/uv/)
- pandas
- PyMuPDF

The committed dependency lock file is the reproducible default for the project's declared dependencies.

```bash
uv sync --locked --all-extras
uv run pytest -q
uv run ruff check .
uv run python scripts/check_project.py
```

A conventional Python virtual environment can also be used:

```bash
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

The official damage-processing scripts additionally require pandas and PyMuPDF if these packages are not already included in the installed environment.

### Official Damage Dataset Processing

Place authorized source PDFs in the following local structure:

```text
data/raw/official_damage/
├── person_01/
├── person_02/
└── person_03/
```

Run the extraction pipeline:

```bash
python scripts/08_build_official_dataset.py
```

Run dataset validation and integration:

```bash
python scripts/09_validate_and_merge.py
```

Principal local outputs:

```text
data/interim/official_damage/
└── official_damage_records.csv

data/final/
├── malatya_damage_dataset.csv
└── malatya_damage_analysis_ready.csv

reports/sprint_00-09/
├── summary.json
├── person_summary.csv
├── damage_class_distribution.csv
├── duplicate_candidates.csv
├── damage_conflicts.csv
├── missing_mahalle.csv
├── invalid_records.csv
└── review_records.csv
```

The `analysis_ready` filename indicates that automated baseline validation has been applied. Further scientific checks, feature validation, and leakage analysis remain necessary before model training.

Source records and generated building-level datasets are not distributed through this repository unless appropriate permissions and legal grounds are established.

## Evaluation Principles

Damage categories are imbalanced and have a meaningful severity ordering.

Accuracy alone is insufficient.

Planned evaluation measures include:

- Macro F1
- Per-class precision and recall
- Confusion matrix
- Balanced accuracy
- Ordinal-aware classification error
- Cross-validation where appropriate
- Spatial or grouped holdout evaluation

Special attention will be given to avoiding information leakage across records representing the same building, neighbourhood, or geographical area.

A model trained solely on administrative identifiers or location labels would not establish meaningful engineering-level predictive capability.

## Reproducibility

The project aims to ensure reproducibility through:

- Version-controlled processing scripts
- Documented data sources
- Fixed experiment configurations
- Preserved raw inputs
- Source-file traceability
- Automated validation reports
- Recorded library and dependency versions
- Explicit dataset and model limitations

Third-party datasets must be obtained from their respective authorized sources and verified against documented validation evidence.

## Responsible Use

This repository is intended exclusively for academic research, exploratory analysis, and decision-support development.

Predictions must not be interpreted as certified structural safety assessments.

Any practical or operational application requires independent validation and review by appropriately qualified civil and earthquake engineering professionals.

The models are not designed to replace official damage assessment procedures.

## License

The repository's source code is governed by the terms of its [LICENSE](LICENSE) file.

Dataset, map, imagery, and pretrained-model licenses are separate and must be reviewed before redistribution.

