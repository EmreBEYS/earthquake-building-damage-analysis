# Sprint 00-15 — Gerçek Hasar Haritası

## Outcome

Sprint 00-15 adds a dedicated Streamlit page for comparing official damage-assessment aggregates
with Copernicus EMSR648 mapped-damage polygons. The two sources remain independent layers and are
never joined or relabelled at building level.

The official processed PDF schema contains neighborhood, street and building-number text, but no
latitude/longitude pair, point, polygon or other reviewed coordinate evidence. The pipeline
therefore applies the sprint rule conservatively: all 46,563 official records are aggregated to
87 reviewed neighborhood boundaries. Address text is not geocoded and no artificial building
point is created.

## Map controls

- six official damage-class filters and a minimum-record threshold;
- neighborhood colors based on the combined `heavy + urgent demolition + destroyed` record share,
  using `%0–10`, `%10–25`, `%25–40` and `%40+` threshold bands instead of a dominant class;
- an optional minimum combined severe-share threshold;
- independent Copernicus damage-class filters;
- discrete legend entries prefixed with `Resmî` and `Copernicus`;
- neighborhood statistics for all six official classes;
- Esri World Imagery satellite basemap with attribution, plus a street-map alternative;
- an evidence panel exposing mapping level, coordinate evidence and source-separation flags.

Satellite imagery is visual context only. It is not an official damage decision and is not used
to infer a new label.

## Data contract

`data/dashboard/sprint_00-15/official_damage_neighborhoods.geojson` contains only reviewed
neighborhood polygons and aggregate official counts. Every feature carries
`mapping_level=neighborhood` and `coordinate_evidence=false`.

`official_neighborhood_statistics.csv` contains the same six-class counts in tabular form.
`manifest.json` keeps the official output and the existing Copernicus GeoJSON as separate source
roles. `validation_report.json` records counts, class totals, source hashes, WGS84 geometry checks,
and the negative building-level join assertion.

## Reproduction

```powershell
uv sync --locked --all-extras
uv run python scripts/13_prepare_real_damage_map.py
uv run pytest -q
uv run ruff check .
uv run streamlit run dashboard.py
```

Expected validated totals are 46,563 official records, 87 official neighborhood aggregates and
3,617 displayable Copernicus polygons. The six official class totals are 10,131 no-damage, 20,706
slight-damage, 1,593 moderate-damage, 12,276 heavy-damage, 955 urgent-demolition and 902 destroyed
records.

