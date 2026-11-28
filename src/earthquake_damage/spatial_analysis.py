"""Sprint 00-20 — neighbourhood spatial analysis and comparison.

Combines independent neighbourhood-level evidence without merging their meanings:

* official Ministry damage aggregates (Sprint 00-15; name-matched, no coordinates);
* Copernicus EMSR648 mapped damage (independent remote-sensing interpretation);
* the Sprint 00-17 exploratory model predictions;
* OSM building density and the 2023→2026 reconstruction change (Sprint 00-19);
* 2022→2023 Sentinel-2 spectral change candidates (Sprint 00-18).

Spatial clustering uses queen contiguity, global Moran's I, local Moran (LISA) and
Getis-Ord Gi*. Pseudo p-values come from seeded permutations; Gi* also gets a
Benjamini–Hochberg false-discovery-rate flag because 87 local tests are run at once.
The statistics are implemented here in NumPy and unit-tested against hand-computed
values, so no extra dependency is needed.
"""

from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path

import numpy as np

HOTSPOT_LABELS_TR = {
    "hot_99": "Sıcak nokta (%99 güven)",
    "hot_95": "Sıcak nokta (%95 güven)",
    "hot_90": "Sıcak nokta (%90 güven)",
    "cold_99": "Soğuk nokta (%99 güven)",
    "cold_95": "Soğuk nokta (%95 güven)",
    "cold_90": "Soğuk nokta (%90 güven)",
    "not_significant": "Anlamlı değil",
    "no_data": "Veri yok",
}
LISA_LABELS_TR = {
    "HH": "Yüksek-Yüksek küme",
    "LL": "Düşük-Düşük küme",
    "HL": "Yüksek değer, düşük komşular",
    "LH": "Düşük değer, yüksek komşular",
    "not_significant": "Anlamlı değil",
    "no_data": "Veri yok",
}


# ---------------------------------------------------------------------------
# Spatial weights and statistics (pure, unit-tested)
# ---------------------------------------------------------------------------


def contiguity_neighbors(geometries, tolerance: float = 0.0) -> list[np.ndarray]:
    """Queen contiguity: polygons that touch or overlap after a small metric buffer.

    The buffer absorbs slivers and gaps between independently digitised boundaries.
    """
    from shapely.strtree import STRtree

    shapes = [geometry.buffer(tolerance) if tolerance else geometry for geometry in geometries]
    tree = STRtree(shapes)
    neighbors = []
    for index, shape in enumerate(shapes):
        candidates = tree.query(shape, predicate="intersects")
        neighbors.append(np.array(sorted(int(c) for c in candidates if c != index), dtype=int))
    return neighbors


def subset_neighbors(neighbors: list[np.ndarray], keep: np.ndarray) -> list[np.ndarray]:
    """Restrict a neighbour list to the units where ``keep`` is True, re-indexed."""
    keep = np.asarray(keep, dtype=bool)
    new_index = np.full(len(keep), -1, dtype=int)
    new_index[keep] = np.arange(int(keep.sum()))
    return [
        np.array([new_index[j] for j in neighbors[i] if keep[j]], dtype=int)
        for i in np.flatnonzero(keep)
    ]


def _spatial_lag(values: np.ndarray, neighbors: list[np.ndarray]) -> np.ndarray:
    """Row-standardised lag; units without neighbours get NaN."""
    return np.array(
        [values[n].mean() if len(n) else np.nan for n in neighbors], dtype=float
    )


def global_morans_i(
    values, neighbors: list[np.ndarray], permutations: int = 999, seed: int = 0
) -> dict:
    """Global Moran's I with row-standardised weights and a permutation pseudo p-value."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    has_neighbors = np.array([len(nb) > 0 for nb in neighbors])

    def statistic(sample: np.ndarray) -> float:
        z = sample - sample.mean()
        denominator = float(z @ z)
        if denominator == 0:
            return float("nan")
        lag = _spatial_lag(z, neighbors)
        s0 = float(has_neighbors.sum())  # each non-island row sums to one
        return float(n / s0 * np.nansum(z * lag) / denominator)

    observed = statistic(x)
    rng = np.random.default_rng(seed)
    simulated = np.array([statistic(rng.permutation(x)) for _ in range(permutations)])
    expected = -1.0 / (n - 1)
    if observed >= expected:
        extreme = int((simulated >= observed).sum())
    else:
        extreme = int((simulated <= observed).sum())
    return {
        "I": observed,
        "expected_I": expected,
        "z_sim": float((observed - simulated.mean()) / simulated.std(ddof=1)),
        "p_sim": (extreme + 1) / (permutations + 1),
        "permutations": permutations,
        "n": n,
    }


def local_morans_i(
    values, neighbors: list[np.ndarray], permutations: int = 999, seed: int = 0
) -> dict[str, np.ndarray]:
    """Local Moran (LISA) with conditional-permutation pseudo p-values and quadrants."""
    x = np.asarray(values, dtype=float)
    n = len(x)
    z = x - x.mean()
    m2 = float(z @ z) / n
    lag = _spatial_lag(z, neighbors)
    local = z * lag / m2 if m2 else np.full(n, np.nan)
    rng = np.random.default_rng(seed)
    p_values = np.full(n, np.nan)
    for i in range(n):
        k = len(neighbors[i])
        if k == 0 or m2 == 0:
            continue
        others = np.delete(z, i)
        draws = np.array([rng.choice(others, size=k, replace=False).mean()
                          for _ in range(permutations)])
        simulated = z[i] * draws / m2
        if local[i] >= 0:
            extreme = int((simulated >= local[i]).sum())
        else:
            extreme = int((simulated <= local[i]).sum())
        p_values[i] = (extreme + 1) / (permutations + 1)
    quadrant = np.where(
        np.isnan(lag),
        "no_data",
        np.where(z >= 0, np.where(lag >= 0, "HH", "HL"), np.where(lag >= 0, "LH", "LL")),
    )
    return {"I": local, "p_sim": p_values, "quadrant": quadrant, "lag": lag}


def getis_ord_gi_star(values, neighbors: list[np.ndarray]) -> dict[str, np.ndarray]:
    """Getis-Ord Gi* with binary weights that include the unit itself.

    z_i = (Σ_j w_ij x_j − x̄ Σ_j w_ij) / (S √((n Σ_j w_ij² − (Σ_j w_ij)²) / (n − 1)))
    """
    from scipy.stats import norm

    x = np.asarray(values, dtype=float)
    n = len(x)
    mean = x.mean()
    spread = math.sqrt(max(float((x**2).mean() - mean**2), 0.0))
    z_scores = np.full(n, np.nan)
    for i in range(n):
        members = np.append(neighbors[i], i)
        weight_sum = len(members)
        variance_term = (n * weight_sum - weight_sum**2) / (n - 1)
        if len(neighbors[i]) == 0 or spread == 0 or variance_term <= 0:
            continue
        z_scores[i] = (x[members].sum() - mean * weight_sum) / (
            spread * math.sqrt(variance_term)
        )
    p_values = 2 * norm.sf(np.abs(z_scores))
    return {"z": z_scores, "p": p_values}


def benjamini_hochberg(p_values, alpha: float = 0.05) -> np.ndarray:
    """Return a boolean mask of discoveries at false-discovery rate ``alpha``; NaN → False."""
    p = np.asarray(p_values, dtype=float)
    valid = ~np.isnan(p)
    result = np.zeros(len(p), dtype=bool)
    if not valid.any():
        return result
    order = np.argsort(p[valid])
    ranked = p[valid][order]
    m = len(ranked)
    passed = ranked <= alpha * np.arange(1, m + 1) / m
    if passed.any():
        cutoff = ranked[np.flatnonzero(passed).max()]
        result[np.flatnonzero(valid)] = p[valid] <= cutoff
    return result


def hotspot_class(z: float, p: float, levels=(0.01, 0.05, 0.10)) -> str:
    """ArcGIS-style confidence bins for one Gi* result."""
    if z is None or p is None or math.isnan(z) or math.isnan(p):
        return "no_data"
    for level in sorted(levels):
        if p < level:
            confidence = round((1 - level) * 100)
            return f"{'hot' if z > 0 else 'cold'}_{confidence}"
    return "not_significant"


def lisa_class(quadrant: str, p: float, alpha: float = 0.05) -> str:
    if quadrant == "no_data" or p is None or math.isnan(p):
        return "no_data"
    return quadrant if p < alpha else "not_significant"


def grid_cells(bounds: tuple[float, float, float, float], size: float):
    """Square cells covering ``bounds`` (metric), with (row, col) for rook/queen adjacency."""
    from shapely.geometry import box

    west, south, east, north = bounds
    columns = max(1, math.ceil((east - west) / size))
    rows = max(1, math.ceil((north - south) / size))
    cells = []
    for row in range(rows):
        for column in range(columns):
            x0 = west + column * size
            y0 = south + row * size
            cells.append((row, column, box(x0, y0, x0 + size, y0 + size)))
    return cells


def grid_queen_neighbors(rows: np.ndarray, columns: np.ndarray) -> list[np.ndarray]:
    """Queen adjacency among the given cells by integer (row, col) position."""
    lookup = {(int(r), int(c)): i for i, (r, c) in enumerate(zip(rows, columns, strict=True))}
    neighbors = []
    for r, c in zip(rows, columns, strict=True):
        found = [
            lookup[(int(r) + dr, int(c) + dc)]
            for dr in (-1, 0, 1)
            for dc in (-1, 0, 1)
            if (dr or dc) and (int(r) + dr, int(c) + dc) in lookup
        ]
        neighbors.append(np.array(sorted(found), dtype=int))
    return neighbors


# ---------------------------------------------------------------------------
# Neighbourhood comparison
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _points_to_neighborhoods(frame, neighborhoods, name_field: str):
    """Attach each feature's neighbourhood by representative point (``unknown`` outside)."""
    import geopandas as gpd

    points = gpd.GeoDataFrame(
        frame.drop(columns="geometry"),
        geometry=frame.geometry.representative_point(),
        crs=frame.crs,
    )
    joined = gpd.sjoin(
        points, neighborhoods[[name_field, "geometry"]], how="left", predicate="within"
    )
    joined = joined[~joined.index.duplicated(keep="first")]
    return joined[name_field].fillna("unknown")


def build_comparison(root: Path, config: dict):
    """Neighbourhood comparison table (metric CRS GeoDataFrame) and input provenance."""
    import geopandas as gpd
    import pandas as pd

    metric = config["metric_crs"]
    name = config["neighborhood_name_field"]
    hoods = gpd.read_file(root / config["neighborhoods"]).to_crs(metric)
    hoods = hoods[["neighborhood_id", name, "aoi_coverage_ratio", "coverage_group", "geometry"]]
    hoods = hoods.reset_index(drop=True)
    hoods["area_km2"] = hoods.geometry.area / 1e6

    # Official Ministry aggregates (already per neighbourhood, by id).
    official = pd.read_csv(root / config["official_statistics"])
    official = official.rename(
        columns={"official_total": "official_records", "severe_count": "official_severe",
                 "severe_ratio": "official_severe_ratio"}
    )[["neighborhood_id", "official_records", "official_severe", "official_severe_ratio",
       "no_damage", "slight_damage", "moderate_damage", "heavy_damage",
       "urgent_demolition", "destroyed"]]
    official = official.rename(
        columns={c: f"official_{c}" for c in ("no_damage", "slight_damage", "moderate_damage",
                                              "heavy_damage", "urgent_demolition", "destroyed")}
    )
    table = hoods.merge(official, on="neighborhood_id", how="left", validate="one_to_one")
    if table["official_records"].isna().any():
        raise ValueError("Official statistics missing for some neighbourhoods")
    table["official_records_per_km2"] = table["official_records"] / table["area_km2"]
    table["official_severe_per_km2"] = table["official_severe"] / table["area_km2"]

    # Copernicus EMSR648 mapped damage, attributed by representative point.
    copernicus = gpd.read_file(root / config["copernicus"]).to_crs(metric)
    copernicus["hood"] = _points_to_neighborhoods(copernicus, hoods, name).to_numpy()
    severe_grades = set(config["severe_copernicus_grades"])
    copernicus["severe"] = copernicus["damage_grade"].isin(severe_grades)
    emsr = copernicus.groupby("hood").agg(
        emsr_buildings=("severe", "size"), emsr_severe=("severe", "sum"),
        emsr_destroyed=("damage_grade", lambda s: int((s == "Destroyed").sum())),
    )
    table = table.merge(emsr, left_on=name, right_index=True, how="left")
    for column in ("emsr_buildings", "emsr_severe", "emsr_destroyed"):
        table[column] = table[column].fillna(0).astype(int)
    covered = table["aoi_coverage_ratio"].fillna(0) >= config["copernicus_minimum_coverage_ratio"]
    table["emsr_coverage_sufficient"] = covered & (table["emsr_buildings"] > 0)
    table["emsr_severe_share"] = np.where(
        table["emsr_coverage_sufficient"],
        table["emsr_severe"] / table["emsr_buildings"].where(table["emsr_buildings"] > 0),
        np.nan,
    )

    # Sprint 00-17 exploratory predictions on the same EMSR648 footprints.
    predictions = gpd.read_file(root / config["predictions"]).to_crs(metric)
    predictions["hood"] = _points_to_neighborhoods(predictions, hoods, name).to_numpy()
    predictions["severe"] = predictions["predicted_damage"].isin(
        set(config["severe_predicted_classes"])
    )
    predicted = predictions.groupby("hood").agg(
        predicted_buildings=("severe", "size"), predicted_severe=("severe", "sum"),
        predicted_low_confidence=("low_confidence", "sum"),
    )
    table = table.merge(predicted, left_on=name, right_index=True, how="left")
    for column in ("predicted_buildings", "predicted_severe", "predicted_low_confidence"):
        table[column] = table[column].fillna(0).astype(int)
    table["predicted_severe_share"] = np.where(
        table["emsr_coverage_sufficient"],
        table["predicted_severe"] / table["predicted_buildings"].where(
            table["predicted_buildings"] > 0
        ),
        np.nan,
    )

    # Sprint 00-19 OSM density and reconstruction indicators.
    recon = pd.read_csv(root / config["reconstruction_indicators"])
    recon = recon[recon["neighborhood"] != "unknown"][
        ["neighborhood", "osm_buildings_2023", "osm_buildings_2026", "footprint_area_2023_m2",
         "footprint_area_2026_m2", "net_footprint_area_change_pct", "removed_candidates",
         "removed_share_of_2023_pct", "new_candidates", "new_footprint_density_per_km2",
         "renewal_turnover_pct", "spectral_change_share_pct"]
    ].rename(columns={"spectral_change_share_pct": "spectral_change_2023_2026_pct"})
    table = table.merge(recon, left_on=name, right_on="neighborhood", how="left",
                        validate="one_to_one").drop(columns="neighborhood")
    if table["osm_buildings_2023"].isna().any():
        raise ValueError("Reconstruction indicators missing for some neighbourhoods")
    table["building_density_2023_km2"] = table["osm_buildings_2023"] / table["area_km2"]
    # Net loss complements the removed share: footprints replaced through splits or merges
    # stay "uncertain" in the conservative one-to-one matching and are not counted as removed.
    table["net_building_loss_pct"] = np.where(
        table["osm_buildings_2023"] > 0,
        100 * (table["osm_buildings_2023"] - table["osm_buildings_2026"])
        / table["osm_buildings_2023"].where(table["osm_buildings_2023"] > 0),
        np.nan,
    )
    table["footprint_coverage_2023_pct"] = (
        100 * table["footprint_area_2023_m2"] / (table["area_km2"] * 1e6)
    )

    # Sprint 00-18 spectral candidates (2022→2023), area share of each neighbourhood.
    spectral = gpd.read_file(root / config["spectral_change_2022_2023"]).to_crs(metric)
    pieces = gpd.overlay(
        spectral[["geometry"]], hoods[[name, "geometry"]], how="intersection", keep_geom_type=True
    )
    spectral_area = pieces.assign(a=pieces.geometry.area).groupby(name)["a"].sum()
    table["spectral_change_2022_2023_pct"] = (
        100 * table[name].map(spectral_area).fillna(0) / (table["area_km2"] * 1e6)
    )

    provenance = {
        key: {"path": config[key], "sha256": _sha256(root / config[key])}
        for key in ("neighborhoods", "official_statistics", "copernicus", "predictions",
                    "spectral_change_2022_2023", "reconstruction_indicators")
    }
    counts = {
        "copernicus_unassigned": int((copernicus["hood"] == "unknown").sum()),
        "copernicus_total": len(copernicus),
        "predictions_total": len(predictions),
        "spectral_components": len(spectral),
    }
    return table, provenance, counts


# ---------------------------------------------------------------------------
# Hot spots
# ---------------------------------------------------------------------------


def neighborhood_hotspots(table, config: dict) -> tuple[dict, list[dict]]:
    """Add Gi*/LISA columns per configured variable; return them and global Moran rows."""
    neighbors = contiguity_neighbors(
        list(table.geometry), config["contiguity_tolerance_metres"]
    )
    permutations = int(config["permutations"])
    seed = int(config["random_seed"])
    levels = config["significance_levels"]
    columns: dict[str, np.ndarray] = {}
    summary = []
    for offset, variable in enumerate(config["hotspot_variables"]):
        values = table[variable].to_numpy(dtype=float)
        keep = ~np.isnan(values)
        local_neighbors = subset_neighbors(neighbors, keep)
        gi = getis_ord_gi_star(values[keep], local_neighbors)
        lisa = local_morans_i(values[keep], local_neighbors, permutations, seed + offset)
        moran = global_morans_i(values[keep], local_neighbors, permutations, seed + offset)
        fdr = benjamini_hochberg(gi["p"], config["fdr_alpha"])

        def expand(array, fill, dtype=float):
            full = np.full(len(values), fill, dtype=dtype)
            full[keep] = array
            return full

        z, p = expand(gi["z"], np.nan), expand(gi["p"], np.nan)
        columns[f"{variable}__gi_z"] = z
        columns[f"{variable}__gi_p"] = p
        columns[f"{variable}__gi_fdr"] = expand(fdr, False, bool)
        columns[f"{variable}__hotspot"] = np.array(
            [hotspot_class(a, b, levels) for a, b in zip(z, p, strict=True)], dtype=object
        )
        lisa_p = expand(lisa["p_sim"], np.nan)
        quadrant = expand(lisa["quadrant"], "no_data", object)
        columns[f"{variable}__lisa_p"] = lisa_p
        columns[f"{variable}__lisa"] = np.array(
            [lisa_class(q, pv) for q, pv in zip(quadrant, lisa_p, strict=True)], dtype=object
        )
        hot = columns[f"{variable}__hotspot"]
        summary.append(
            {
                "variable": variable,
                "label_tr": config["hotspot_variables"][variable],
                "units": int(keep.sum()),
                "morans_i": round(moran["I"], 4),
                "expected_i": round(moran["expected_I"], 4),
                "z_sim": round(moran["z_sim"], 3),
                "p_sim": moran["p_sim"],
                "hot_spots_95": int(np.isin(hot, ["hot_99", "hot_95"]).sum()),
                "cold_spots_95": int(np.isin(hot, ["cold_99", "cold_95"]).sum()),
                "gi_fdr_significant": int(fdr.sum()),
                "lisa_hh": int((columns[f"{variable}__lisa"] == "HH").sum()),
                "lisa_ll": int((columns[f"{variable}__lisa"] == "LL").sum()),
                "lisa_outliers": int(np.isin(columns[f"{variable}__lisa"], ["HL", "LH"]).sum()),
            }
        )
    return columns, summary


def grid_hotspots(root: Path, config: dict, hoods) -> tuple[object, dict]:
    """500 m grid Gi* for EMSR648 severe share and 2023→2026 removed-candidate share."""
    import geopandas as gpd
    import pandas as pd

    metric = config["metric_crs"]
    grid_config = config["grid"]
    aoi = hoods.geometry.union_all()
    cells = grid_cells(aoi.bounds, float(grid_config["cell_size_metres"]))
    grid = gpd.GeoDataFrame(
        {"row": [c[0] for c in cells], "col": [c[1] for c in cells]},
        geometry=[c[2] for c in cells], crs=metric,
    )
    grid = grid[grid.intersects(aoi)].reset_index(drop=True)
    grid["cell_id"] = [f"r{r:03d}c{c:03d}" for r, c in zip(grid["row"], grid["col"], strict=True)]

    def count_points(frame, mask=None):
        points = gpd.GeoDataFrame(geometry=frame.geometry.representative_point(), crs=metric)
        if mask is not None:
            points = points[np.asarray(mask)]
        joined = gpd.sjoin(points, grid[["geometry"]], predicate="within")
        return joined.groupby("index_right").size().reindex(grid.index, fill_value=0)

    copernicus = gpd.read_file(root / config["copernicus"]).to_crs(metric)
    grid["emsr_buildings"] = count_points(copernicus)
    grid["emsr_severe"] = count_points(
        copernicus, copernicus["damage_grade"].isin(config["severe_copernicus_grades"])
    )
    snapshot = root / config["osm_post_event_snapshot"]
    recon = gpd.read_parquet(root / config["reconstruction_map"]).to_crs(metric)
    removed = recon[recon["reconstruction_class"] == "removed_candidate"]
    grid["removed_candidates"] = count_points(removed)
    if snapshot.exists():
        osm = gpd.read_file(snapshot).to_crs(metric)
        grid["osm_buildings_2023"] = count_points(osm)
        snapshot_hash = _sha256(snapshot)
    else:  # the raw snapshot is git-ignored; without it the removed-share grid is skipped
        grid["osm_buildings_2023"] = 0
        snapshot_hash = None

    variables = {
        "emsr_severe_share": (grid["emsr_severe"], grid["emsr_buildings"],
                              int(grid_config["minimum_copernicus_buildings"])),
        "removed_share": (grid["removed_candidates"], grid["osm_buildings_2023"],
                          int(grid_config["minimum_buildings"])),
    }
    report = {}
    for offset, (variable, (numerator, denominator, minimum)) in enumerate(variables.items()):
        keep = (denominator >= minimum).to_numpy()
        share = np.where(keep, numerator / denominator.where(denominator > 0), np.nan)
        grid[variable] = share
        z_full = np.full(len(grid), np.nan)
        p_full = np.full(len(grid), np.nan)
        fdr_full = np.zeros(len(grid), dtype=bool)
        if keep.sum() >= 3:
            neighbors = grid_queen_neighbors(grid["row"][keep].to_numpy(),
                                             grid["col"][keep].to_numpy())
            gi = getis_ord_gi_star(share[keep], neighbors)
            z_full[keep], p_full[keep] = gi["z"], gi["p"]
            fdr_full[keep] = benjamini_hochberg(gi["p"], config["fdr_alpha"])
        grid[f"{variable}__gi_z"] = z_full
        grid[f"{variable}__gi_p"] = p_full
        grid[f"{variable}__gi_fdr"] = fdr_full
        grid[f"{variable}__hotspot"] = [
            hotspot_class(z, p, config["significance_levels"])
            for z, p in zip(z_full, p_full, strict=True)
        ]
        classes = pd.Series(grid[f"{variable}__hotspot"]).value_counts().to_dict()
        report[variable] = {"cells_analysed": int(keep.sum()), "minimum_denominator": minimum,
                            "hotspot_counts": {k: int(v) for k, v in classes.items()},
                            "fdr_significant": int(fdr_full.sum())}
    report["cells_total"] = len(grid)
    report["cell_size_metres"] = grid_config["cell_size_metres"]
    report["osm_post_event_snapshot_sha256"] = snapshot_hash
    grid = grid[(grid["emsr_buildings"] > 0) | (grid["osm_buildings_2023"] > 0)
                | (grid["removed_candidates"] > 0)].reset_index(drop=True)
    return grid, report


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def run(root: Path, config: dict) -> dict:
    import geopandas as gpd
    import pandas as pd

    table, provenance, counts = build_comparison(root, config)
    hot_columns, moran_summary = neighborhood_hotspots(table, config)
    for column, values in hot_columns.items():
        table[column] = values
    name = config["neighborhood_name_field"]

    ranked = {
        "official_severe_ratio": "rank_official_severe_ratio",
        "official_severe_per_km2": "rank_official_severe_density",
        "building_density_2023_km2": "rank_building_density",
        "removed_share_of_2023_pct": "rank_removed_share",
        "net_building_loss_pct": "rank_net_building_loss",
    }
    for variable, rank_column in ranked.items():
        table[rank_column] = table[variable].rank(ascending=False, method="min").astype("Int64")

    # Agreement between independent sources, as rank correlation only.
    def spearman(a: str, b: str) -> dict:
        pair = table[[a, b]].dropna()
        varies = len(pair) > 2 and pair[a].nunique() > 1 and pair[b].nunique() > 1
        rho = pair[a].rank().corr(pair[b].rank()) if varies else float("nan")  # undefined
        return {"a": a, "b": b, "n": len(pair), "spearman_rho": round(float(rho), 4)}

    correlations = [
        spearman("official_severe_ratio", "emsr_severe_share"),
        spearman("official_severe_ratio", "predicted_severe_share"),
        spearman("emsr_severe_share", "predicted_severe_share"),
        spearman("official_severe_ratio", "removed_share_of_2023_pct"),
        spearman("official_severe_ratio", "net_building_loss_pct"),
        spearman("removed_share_of_2023_pct", "net_building_loss_pct"),
        spearman("official_severe_per_km2", "removed_candidates"),
        spearman("building_density_2023_km2", "official_severe_per_km2"),
        spearman("official_severe_ratio", "spectral_change_2022_2023_pct"),
    ]

    grid, grid_report = grid_hotspots(root, config, table[[name, "geometry"]])

    output = root / config["output_directory"]
    output.mkdir(parents=True, exist_ok=True)
    report_dir = root / config["report_directory"]
    report_dir.mkdir(parents=True, exist_ok=True)

    csv_table = table.drop(columns="geometry").copy()
    float_columns = csv_table.select_dtypes("float").columns
    csv_table[float_columns] = csv_table[float_columns].round(4)
    comparison_path = output / "neighborhood_comparison.csv"
    csv_table.to_csv(lineterminator="\n", path_or_buf=comparison_path, index=False, encoding="utf-8")

    web = table.to_crs(4326)
    web[float_columns] = web[float_columns].round(4)
    for variable in config["hotspot_variables"]:
        web[f"{variable}__hotspot_tr"] = web[f"{variable}__hotspot"].map(HOTSPOT_LABELS_TR)
        web[f"{variable}__lisa_tr"] = web[f"{variable}__lisa"].map(LISA_LABELS_TR)
    layer_path = output / "neighborhood_spatial_analysis.geojson"
    web.to_file(layer_path, driver="GeoJSON")

    grid_web = grid.to_crs(4326)
    grid_floats = grid_web.select_dtypes("float").columns
    grid_web[grid_floats] = grid_web[grid_floats].round(4)
    grid_path = output / "hotspot_grid.geojson"
    grid_web.to_file(grid_path, driver="GeoJSON")

    summary_path = output / "spatial_autocorrelation_summary.csv"
    pd.DataFrame(moran_summary).to_csv(lineterminator="\n", path_or_buf=summary_path, index=False, encoding="utf-8")

    reopened = gpd.read_file(layer_path)
    if len(reopened) != len(table) or not reopened.geometry.is_valid.all():
        raise ValueError("Neighbourhood layer roundtrip failed")
    if len(gpd.read_file(grid_path)) != len(grid):
        raise ValueError("Grid layer roundtrip failed")
    if int(table["official_records"].sum()) != int(
        pd.read_csv(root / config["official_statistics"])["official_total"].sum()
    ):
        raise ValueError("Official record totals not conserved")

    report = {
        "status": "completed_spatial_analysis",
        "generated_at_utc": datetime.now(UTC).isoformat(),
        "neighborhoods": len(table),
        "weights": {
            "type": "queen contiguity (buffered intersects)",
            "tolerance_metres": config["contiguity_tolerance_metres"],
            "islands": int(sum(len(n) == 0 for n in contiguity_neighbors(
                list(table.geometry), config["contiguity_tolerance_metres"]))),
        },
        "permutations": config["permutations"],
        "random_seed": config["random_seed"],
        "global_morans_i": moran_summary,
        "source_rank_correlations": correlations,
        "grid": grid_report,
        "counts": counts,
        "copernicus_neighborhoods_with_sufficient_coverage": int(
            table["emsr_coverage_sufficient"].sum()
        ),
        "inputs": provenance,
        "outputs_sha256": {
            path.name: _sha256(path)
            for path in (comparison_path, layer_path, grid_path, summary_path)
        },
        "roundtrip_valid": True,
        "limitations": [
            "Official records are name-matched neighbourhood aggregates without coordinates; "
            "densities assume records belong to the whole neighbourhood polygon.",
            "EMSR648 covers only part of the study area; its shares are reported only where at "
            f"least {config['copernicus_minimum_coverage_ratio']:.0%} of the neighbourhood is "
            "inside the activation AOI.",
            "Neighbourhoods differ greatly in size and record count (modifiable areal unit "
            "problem); hot spots depend on this zoning and on the contiguity definition.",
            "87 simultaneous local tests inflate false positives; use the FDR flag for "
            "confirmatory statements.",
            "Sprint 00-17 predictions are exploratory (spatial macro-F1 0.24) and are compared, "
            "never used as ground truth. They cover the same EMSR648 footprints the model was "
            "trained on, so their high agreement with EMSR648 shares is largely in-sample and "
            "is not validation.",
            "Rank correlations describe agreement between sources, not causation.",
        ],
    }
    (report_dir / "spatial_analysis_validation.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report
