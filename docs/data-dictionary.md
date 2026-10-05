# Data Dictionary

This is a provisional dictionary for the planned analytical dataset. Names and
definitions must be reconciled with the selected source files before the first
processed dataset is produced. The final row grain (for example, one row per
district and earthquake event) must also be documented.

| Column | Planned type | Unit / values | Provisional definition | Validation notes |
|---|---|---|---|---|
| `province` | string | Province name | Province containing the observation | Required; standardize spelling and Turkish characters |
| `district` | string | District name | District containing the observation | Required for district-level rows; verify province–district mapping |
| `population` | integer | People | Resident population for the selected reference year | Non-negative; record reference year and source |
| `total_buildings` | integer | Buildings | Total number of buildings in the observation area | Non-negative; confirm whether this means surveyed or all buildings |
| `collapsed_buildings` | integer | Buildings | Buildings classified as collapsed | Non-negative; use the source's official label definition |
| `heavy_damaged_buildings` | integer | Buildings | Buildings classified as heavily damaged | Non-negative; use the source's official label definition |
| `moderate_damaged_buildings` | integer | Buildings | Buildings classified as moderately damaged | Non-negative; use the source's official label definition |
| `slightly_damaged_buildings` | integer | Buildings | Buildings classified as slightly damaged | Non-negative; use the source's official label definition |
| `undamaged_buildings` | integer | Buildings | Buildings classified as undamaged | Non-negative; use the source's official label definition |
| `fatalities` | integer | People | Reported deaths associated with the event and area | Non-negative; definitions and reporting date must be recorded |
| `injured` | integer | People | Reported injured people associated with the event and area | Non-negative; definitions and reporting date must be recorded |
| `earthquake_magnitude` | float | Magnitude scale TBD | Reported magnitude of the associated earthquake event | Record the magnitude scale and reporting agency |
| `distance_to_epicenter` | float | km | Distance between the observation location and event epicenter | Non-negative; document coordinate reference and calculation method |
| `latitude` | float | Decimal degrees | Latitude of the observation location or representative centroid | Range -90 to 90; document what location the coordinate represents |
| `longitude` | float | Decimal degrees | Longitude of the observation location or representative centroid | Range -180 to 180; document what location the coordinate represents |

## Dataset-Level Validation Rules

- Define a unique key once the dataset grain is known.
- Do not mix province-level and district-level rows without an explicit level column.
- Confirm whether damage categories are mutually exclusive and exhaustive.
- If categories are exhaustive, compare their sum with `total_buildings` and explain discrepancies.
- Record missing values explicitly; do not silently convert missing counts to zero.
- Keep raw source column names and transformations in an auditable mapping.
