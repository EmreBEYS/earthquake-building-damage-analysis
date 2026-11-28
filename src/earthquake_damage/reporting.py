"""Sprint 00-23 — reporting and download system.

Four report types share one structure (:class:`Report`) and four exporters:

* neighbourhood report — official damage, EMSR648, density, change, hot spots, rank;
* building report — one EMSR648 polygon with prediction, change and context;
* model performance report — Sprint 00-16 metrics plus a spatial-split confusion matrix
  recomputed here with the exact 00-16 split;
* data quality report — per dataset: rows, completeness, geometry validity, duplicates,
  coverage and checksum.

Exports: CSV (long ``section, key, value`` summary plus tables), Excel (one sheet per table),
PNG (any report figure) and PDF (cover, summary, tables, figures and notes). PNG and PDF
use Matplotlib only, so there is no browser or Kaleido dependency.
"""

from __future__ import annotations

import hashlib
import io
import json
import textwrap
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

OFFICIAL_CLASSES = (
    ("official_no_damage", "Hasarsız", "#3B82F6"),
    ("official_slight_damage", "Az hasarlı", "#22C55E"),
    ("official_moderate_damage", "Orta hasarlı", "#EAB308"),
    ("official_heavy_damage", "Ağır hasarlı", "#F97316"),
    ("official_urgent_demolition", "Acil yıkılacak", "#EF4444"),
    ("official_destroyed", "Yıkık", "#991B1B"),
)
GRADE_ORDER = ("no_visible_damage", "possibly_damaged", "damaged", "destroyed")
GRADE_TR = {
    "no_visible_damage": "Görünür hasar yok",
    "possibly_damaged": "Olası hasarlı",
    "damaged": "Hasarlı",
    "destroyed": "Yıkılmış",
}
DISCLAIMER = (
    "Araştırma amaçlıdır. Resmî hasar, bina güvenliği, tahliye veya güçlendirme kararı "
    "için kullanılamaz. İlişkiler nedensellik kanıtlamaz."
)
PATHS = {
    "comparison": "data/dashboard/sprint_00-20/neighborhood_comparison.csv",
    "neighborhood_layer": "data/dashboard/sprint_00-20/neighborhood_spatial_analysis.geojson",
    "details": "data/dashboard/sprint_00-22/building_details.csv",
    "districts": "data/dashboard/sprint_00-21/neighborhood_districts.csv",
    "emsr648": "data/dashboard/sprint_00-12/copernicus_damage_polygons.geojson",
    "model_comparison": "reports/sprint_00-16/model_comparison.csv",
    "model_report": "reports/sprint_00-16/model_evaluation_report.json",
}


@dataclass
class Report:
    """A report ready for any exporter."""

    kind: str
    title: str
    subtitle: str
    summary: list[tuple[str, str, str]]  # (section, key, value)
    tables: dict[str, pd.DataFrame] = field(default_factory=dict)
    figures: dict[str, object] = field(default_factory=dict)  # name → matplotlib Figure
    notes: list[str] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    )

    def slug(self) -> str:
        cleaned = "".join(c if c.isalnum() else "_" for c in self.subtitle.lower())
        return f"{self.kind}_{cleaned}".strip("_")[:80]


def _fmt(value, digits: int = 2) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    if isinstance(value, (bool, np.bool_)):
        return "evet" if value else "hayır"
    if isinstance(value, (int, np.integer)):
        return f"{int(value):,}".replace(",", ".")
    if isinstance(value, (float, np.floating)):
        return f"{float(value):,.{digits}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return str(value)


def _pct(value) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "—"
    return "%" + f"{float(value) * 100:.1f}".replace(".", ",")


def _cell(value) -> str:
    """Text for one table cell; missing values (NaN, None, pd.NA) become an em dash."""
    try:
        if pd.isna(value):
            return "—"
    except (TypeError, ValueError):  # list-like cells
        pass
    return str(value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


def load_context(root: Path) -> dict:
    """Read every committed input the reports need; missing files raise clearly."""
    import geopandas as gpd

    root = Path(root)
    missing = [p for p in PATHS.values() if not (root / p).exists()]
    if missing:
        raise FileNotFoundError(f"Report inputs missing: {missing}")
    return {
        "root": root,
        "comparison": pd.read_csv(root / PATHS["comparison"]),
        "details": pd.read_csv(root / PATHS["details"]),
        "districts": pd.read_csv(root / PATHS["districts"]),
        "neighborhoods": gpd.read_file(root / PATHS["neighborhood_layer"]),
        "emsr648": gpd.read_file(root / PATHS["emsr648"]),
        "model_comparison": pd.read_csv(root / PATHS["model_comparison"]),
        "model_report": json.loads((root / PATHS["model_report"]).read_text(encoding="utf-8")),
    }


# ---------------------------------------------------------------------------
# Figures (Matplotlib, dark-on-light for print)
# ---------------------------------------------------------------------------


def _figure(width: float = 7.5, height: float = 3.6):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(width, height), dpi=150)
    figure.patch.set_facecolor("white")
    return figure, axis


def official_class_figure(row: pd.Series, title: str):
    figure, axis = _figure()
    labels = [label for _, label, _ in OFFICIAL_CLASSES]
    values = [int(row[key]) for key, _, _ in OFFICIAL_CLASSES]
    bars = axis.barh(labels[::-1], values[::-1],
                     color=[c for _, _, c in OFFICIAL_CLASSES][::-1])
    axis.bar_label(bars, labels=[_fmt(v) for v in values[::-1]], padding=3, fontsize=8)
    axis.set_title(title, fontsize=10)
    axis.set_xlabel("Kayıt")
    axis.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    return figure


def location_figure(neighborhoods, highlight: str, title: str, highlight_geometry=None,
                    context=None, context_column: str | None = None):
    """Small location map: all neighbourhoods in grey, the subject highlighted."""
    figure, axis = _figure(5.5, 5.0)
    metric = neighborhoods.to_crs(32637)
    metric.plot(ax=axis, color="#E5E7EB", edgecolor="#9CA3AF", linewidth=0.4)
    subject = metric[metric["mahalle"] == highlight]
    if context is not None and context_column:
        colors = {"No visible damage": "#3B82F6", "Possibly damaged": "#EAB308",
                  "Damaged": "#F97316", "Destroyed": "#EF4444"}
        context.to_crs(32637).plot(
            ax=axis, color=[colors.get(v, "#94A3B8") for v in context[context_column]],
            linewidth=0,
        )
    subject.plot(ax=axis, facecolor="none", edgecolor="#2F6FDE", linewidth=1.8)
    if highlight_geometry is not None:
        import geopandas as gpd

        gpd.GeoSeries([highlight_geometry], crs=4326).to_crs(32637).plot(
            ax=axis, facecolor="none", edgecolor="black", linewidth=2.2)
        bounds = subject.total_bounds
        pad = max(bounds[2] - bounds[0], bounds[3] - bounds[1]) * 0.15
        axis.set_xlim(bounds[0] - pad, bounds[2] + pad)
        axis.set_ylim(bounds[1] - pad, bounds[3] + pad)
    axis.set_axis_off()
    axis.set_title(title, fontsize=10)
    figure.tight_layout()
    return figure


def probability_figure(building: dict):
    figure, axis = _figure(6, 2.6)
    values = [float(building[f"probability_{g}"]) for g in GRADE_ORDER]
    colors = ["#3B82F6", "#EAB308", "#F97316", "#EF4444"]
    bars = axis.barh([GRADE_TR[g] for g in GRADE_ORDER][::-1], values[::-1], color=colors[::-1])
    axis.bar_label(bars, labels=[_pct(v) for v in values[::-1]], padding=3, fontsize=8)
    axis.set_xlim(0, 1.1)
    axis.set_title("Model sınıf olasılıkları (kalibre edilmemiş)", fontsize=10)
    axis.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    return figure


def confusion_figure(matrix: pd.DataFrame, title: str):
    figure, axis = _figure(5.6, 4.6)
    normalised = matrix.div(matrix.sum(axis=1).replace(0, np.nan), axis=0).fillna(0)
    image = axis.imshow(normalised.to_numpy(), cmap="Blues", vmin=0, vmax=1)
    labels = [GRADE_TR.get(c, c) for c in matrix.columns]
    axis.set_xticks(range(len(labels)), labels, rotation=30, ha="right", fontsize=8)
    axis.set_yticks(range(len(labels)), [GRADE_TR.get(c, c) for c in matrix.index], fontsize=8)
    for i in range(len(matrix.index)):
        for j in range(len(matrix.columns)):
            value = normalised.iat[i, j]
            axis.text(j, i, f"{value:.2f}\n({matrix.iat[i, j]})", ha="center", va="center",
                      fontsize=7, color="white" if value > 0.5 else "black")
    axis.set_xlabel("Tahmin")
    axis.set_ylabel("Gerçek (EMSR648)")
    axis.set_title(title, fontsize=10)
    figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)
    figure.tight_layout()
    return figure


def metric_figure(metrics: pd.DataFrame):
    figure, axis = _figure(7, 3.4)
    splits = {"stratified_random": "Rastgele tabakalı", "spatial_1km_groups": "Mekânsal 1 km"}
    models = list(dict.fromkeys(metrics["model"]))
    width = 0.38
    for offset, (split, label) in enumerate(splits.items()):
        part = metrics[metrics["split"] == split].set_index("model").loc[models]
        x = np.arange(len(models)) + (offset - 0.5) * width
        axis.bar(x, part["macro_f1"], width, label=label,
                 yerr=[part["macro_f1"] - part["macro_f1_ci_lower"],
                       part["macro_f1_ci_upper"] - part["macro_f1"]], capsize=3)
    axis.set_xticks(range(len(models)), models)
    axis.set_ylabel("Macro-F1 (%95 GA)")
    axis.set_ylim(0, 0.6)
    axis.legend(fontsize=8)
    axis.set_title("Model karşılaştırması", fontsize=10)
    axis.spines[["top", "right"]].set_visible(False)
    figure.tight_layout()
    return figure


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------


def neighborhood_report(context: dict, mahalle: str) -> Report:
    table = context["comparison"]
    if mahalle not in set(table["mahalle"]):
        raise KeyError(f"Unknown neighbourhood: {mahalle}")
    row = table.set_index("mahalle").loc[mahalle]
    district = context["districts"].set_index("mahalle")["district"].get(mahalle, "—")
    n = len(table)

    def rank(column: str) -> str:
        value = row.get(column)
        return "—" if pd.isna(value) else f"{int(value)} / {n}"

    from earthquake_damage.spatial_analysis import HOTSPOT_LABELS_TR, LISA_LABELS_TR

    summary = [
        ("Genel", "Mahalle", mahalle),
        ("Genel", "İlçe", district),
        ("Genel", "Alan", f"{_fmt(row['area_km2'])} km²"),
        ("Genel", "Kapsam grubu", str(row["coverage_group"])),
        ("Resmî hasar", "Kayıt", _fmt(int(row["official_records"]))),
        ("Resmî hasar", "Ağır + acil yıkım + yıkık", _fmt(int(row["official_severe"]))),
        ("Resmî hasar", "Ağır hasar oranı", _pct(row["official_severe_ratio"])),
        ("Resmî hasar", "Ağır hasar yoğunluğu", f"{_fmt(row['official_severe_per_km2'], 1)} /km²"),
        ("Resmî hasar", "Oran sırası (87 mahalle)", rank("rank_official_severe_ratio")),
        ("EMSR648", "Poligon", _fmt(int(row["emsr_buildings"]))),
        ("EMSR648", "Hasarlı + yıkılmış payı", _pct(row["emsr_severe_share"])),
        ("EMSR648", "Kapsam yeterli", _fmt(bool(row["emsr_coverage_sufficient"]))),
        ("Model", "Tahmini ağır hasar payı", _pct(row["predicted_severe_share"])),
        ("Yapılaşma", "OSM binası 2023 / 2026",
         f"{_fmt(int(row['osm_buildings_2023']))} / {_fmt(int(row['osm_buildings_2026']))}"),
        ("Yapılaşma", "Bina yoğunluğu 2023", f"{_fmt(row['building_density_2023_km2'], 0)} /km²"),
        ("Değişim", "Kaldırılan yapı payı 2023→2026",
         "%" + _fmt(row["removed_share_of_2023_pct"], 1)),
        ("Değişim", "Net OSM bina kaybı 2023→2026", "%" + _fmt(row["net_building_loss_pct"], 1)),
        ("Değişim", "Yeni yapı adayı", _fmt(int(row["new_candidates"]))),
        ("Değişim", "Spektral değişim 2022→2023", "%" + _fmt(row["spectral_change_2022_2023_pct"], 1)),
        ("Mekânsal", "Gi* (ağır hasar oranı)",
         HOTSPOT_LABELS_TR.get(row["official_severe_ratio__hotspot"], "—")
         + (" · FDR anlamlı" if bool(row["official_severe_ratio__gi_fdr"]) else "")),
        ("Mekânsal", "LISA (ağır hasar oranı)",
         LISA_LABELS_TR.get(row["official_severe_ratio__lisa"], "—")),
        ("Mekânsal", "Gi* (net OSM bina kaybı)",
         HOTSPOT_LABELS_TR.get(row["net_building_loss_pct__hotspot"], "—")
         + (" · FDR anlamlı" if bool(row["net_building_loss_pct__gi_fdr"]) else "")),
    ]
    classes = pd.DataFrame({
        "Sınıf": [label for _, label, _ in OFFICIAL_CLASSES],
        "Kayıt": [int(row[key]) for key, _, _ in OFFICIAL_CLASSES],
    })
    classes["Pay"] = (classes["Kayıt"] / max(int(row["official_records"]), 1)).round(4)
    city = table[["official_severe_ratio", "emsr_severe_share", "building_density_2023_km2",
                  "removed_share_of_2023_pct", "net_building_loss_pct",
                  "spectral_change_2022_2023_pct"]]
    versus = pd.DataFrame({
        "Gösterge": ["Ağır hasar oranı", "EMSR648 ağır pay", "Bina yoğunluğu 2023 (/km²)",
                     "Kaldırılan yapı payı (%)", "Net OSM bina kaybı (%)",
                     "Spektral değişim 2022→2023 (%)"],
        "Mahalle": [row[c] for c in city.columns],
        "87 mahalle medyanı": [city[c].median() for c in city.columns],
    }).round(4)
    buildings = context["details"][context["details"]["mahalle"] == mahalle]
    building_table = buildings[["feature_id", "damage_grade", "predicted_damage", "confidence",
                                "area_m2", "osm_buildings_2023", "removed_by_2026",
                                "reconstruction_status"]].reset_index(drop=True)
    figures = {
        "resmi_hasar_siniflari": official_class_figure(row, f"{mahalle} — resmî hasar sınıfları"),
        "konum": location_figure(context["neighborhoods"], mahalle, f"{mahalle} — konum"),
    }
    return Report(
        kind="mahalle", title="Mahalle analiz raporu", subtitle=mahalle, summary=summary,
        tables={"Resmî hasar sınıfları": classes, "Şehir medyanıyla karşılaştırma": versus,
                "EMSR648 poligonları": building_table},
        figures=figures,
        notes=[
            "Resmî kayıtlar isimle eşleşmiş mahalle toplamlarıdır; koordinat içermez.",
            "EMSR648 payları yalnız AOI kapsamı en az %50 olan mahallelerde hesaplanır.",
            "OSM sayıları haritalama durumudur; yeni yapılar geç çizildiği için eksik sayılabilir.",
            "Kaldırılan yapı payı temkinlidir: bölünen/birleşen ayak izleri 'belirsiz' kalır. "
            "Net OSM bina kaybı bu dönüşümü de yansıtır.",
            "Sıcak nokta sınıfları keşif içindir; doğrulayıcı ifade için FDR bayrağına bakın.",
            DISCLAIMER,
        ],
    )


def building_report(context: dict, feature_id: str) -> Report:
    from earthquake_damage.interactive_map import detail_rows

    details = context["details"].set_index("feature_id")
    if feature_id not in details.index:
        raise KeyError(f"Unknown EMSR648 polygon: {feature_id}")
    building = details.loc[feature_id].to_dict()
    building["feature_id"] = feature_id
    summary = [("Yapı alanı", label, value) for label, value in detail_rows(building)]
    probabilities = pd.DataFrame({
        "Sınıf": [GRADE_TR[g] for g in GRADE_ORDER],
        "Olasılık": [round(float(building[f"probability_{g}"]), 4) for g in GRADE_ORDER],
    })
    neighbours = context["details"][context["details"]["mahalle"] == building["mahalle"]]
    grade_mix = neighbours["damage_grade"].value_counts().rename_axis("EMSR648 sınıfı")
    grade_mix = grade_mix.reset_index(name="Poligon")
    geometry = context["emsr648"].set_index("feature_id").geometry.get(feature_id)
    context_layer = context["emsr648"][context["emsr648"]["feature_id"].isin(
        neighbours["feature_id"])]
    return Report(
        kind="bina", title="Yapı alanı analiz raporu", subtitle=feature_id, summary=summary,
        tables={"Model olasılıkları": probabilities,
                "Mahalledeki EMSR648 dağılımı": grade_mix},
        figures={
            "olasiliklar": probability_figure(building),
            "konum": location_figure(context["neighborhoods"], building["mahalle"],
                                     f"{feature_id} — konum", geometry, context_layer,
                                     "damage_grade"),
        },
        notes=[
            "EMSR648 poligonları yapı alanlarıdır; birden fazla bina içerebilir.",
            "Model tahmini keşif amaçlıdır ve bu poligonlarda eğitilmiştir; doğrulama değildir.",
            DISCLAIMER,
        ],
    )


def spatial_confusion_matrix(root: Path) -> tuple[pd.DataFrame, dict]:
    """Random-forest confusion matrix on the exact Sprint 00-16 spatial (1 km group) split."""
    from sklearn.base import clone
    from sklearn.metrics import confusion_matrix, f1_score

    from earthquake_damage.sprint_00_16 import _load_inputs, _split_indices, load_config

    config = load_config(Path(root) / "configs/sprint_00_16.json")
    inputs = _load_inputs(Path(root), config)
    frame = inputs.spatial_frame
    train, test = _split_indices(frame, config, spatial=True)[:2]
    model = clone(inputs.models["random_forest"])
    model.fit(frame.iloc[train][config["features"]], frame.iloc[train][config["target"]])
    truth = frame.iloc[test][config["target"]].to_numpy()
    predicted = model.predict(frame.iloc[test][config["features"]])
    labels = [g for g in GRADE_ORDER if g in set(frame[config["target"]])]
    matrix = pd.DataFrame(confusion_matrix(truth, predicted, labels=labels),
                          index=labels, columns=labels)
    evidence = {
        "test_rows": int(len(test)),
        "macro_f1": float(f1_score(truth, predicted, labels=labels, average="macro",
                                   zero_division=0)),
        "per_class_f1": dict(zip(labels, np.round(f1_score(
            truth, predicted, labels=labels, average=None, zero_division=0), 4).tolist(),
            strict=True)),
    }
    return matrix, evidence


CONFUSION_CACHE = "reports/sprint_00-23/spatial_confusion_matrix.json"


def cached_confusion_matrix(root: Path) -> tuple[pd.DataFrame, dict]:
    """Recompute when the preserved models exist; otherwise use the committed result."""
    root = Path(root)
    try:
        return spatial_confusion_matrix(root)
    except (FileNotFoundError, OSError) as error:
        cache = root / CONFUSION_CACHE
        if not cache.exists():
            raise FileNotFoundError(
                "Models are not available and no committed confusion matrix exists"
            ) from error
        stored = json.loads(cache.read_text(encoding="utf-8"))
        matrix = pd.DataFrame(stored["matrix"], index=stored["labels"],
                              columns=stored["labels"])
        return matrix, stored["evidence"]


def write_confusion_cache(root: Path) -> dict:
    matrix, evidence = spatial_confusion_matrix(root)
    payload = {"labels": list(matrix.index), "matrix": matrix.to_numpy().tolist(),
               "evidence": evidence, "split": "Sprint 00-16 GroupShuffleSplit, 1 km grid, seed 42",
               "model": "random_forest (cloned from models/random_forest.joblib, refit on train)"}
    path = Path(root) / CONFUSION_CACHE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return payload


def model_performance_report(context: dict) -> Report:
    metrics = context["model_comparison"]
    report = context["model_report"]
    matrix, evidence = cached_confusion_matrix(context["root"])
    reported = metrics[(metrics["split"] == "spatial_1km_groups")
                       & (metrics["model"] == "random_forest")]["macro_f1"].iloc[0]
    spatial = metrics[metrics["split"] == "spatial_1km_groups"].set_index("model")
    summary = [
        ("Veri", "Satır", _fmt(report["dataset"]["spatially_matched_rows"])),
        ("Veri", "Özellikler", ", ".join(report["dataset"]["features"])),
        ("Veri", "Çoğunluk / azınlık oranı",
         _fmt(report["class_imbalance"]["majority_to_minority_ratio"], 1)),
        ("Mekânsal test", "Random forest doğruluk", _fmt(spatial.loc["random_forest", "accuracy"])),
        ("Mekânsal test", "Random forest macro-F1", _fmt(spatial.loc["random_forest", "macro_f1"])),
        ("Mekânsal test", "Dummy macro-F1", _fmt(spatial.loc["dummy", "macro_f1"])),
        ("Mekânsal test", "Karışıklık matrisinden macro-F1",
         _fmt(evidence["macro_f1"], 4) + (" (00-16 ile aynı)" if abs(
             evidence["macro_f1"] - reported) < 1e-9 else f" (00-16: {reported:.4f})")),
        ("Sonuç", "Değerlendirme", report["conclusion"]),
    ]
    per_class = pd.DataFrame({
        "Sınıf": [GRADE_TR[c] for c in evidence["per_class_f1"]],
        "F1": list(evidence["per_class_f1"].values()),
        "Test satırı": matrix.sum(axis=1).to_numpy(),
    })
    matrix_named = matrix.rename(index=GRADE_TR, columns=GRADE_TR)
    matrix_named.index.name = "Gerçek \\ Tahmin"
    return Report(
        kind="model", title="Model performans raporu", subtitle="Sprint 00-16 / 00-17 modelleri",
        summary=summary,
        tables={"Model metrikleri": metrics.round(4),
                "Karışıklık matrisi (mekânsal, random forest)": matrix_named.reset_index(),
                "Sınıf bazında F1": per_class},
        figures={"karisiklik_matrisi": confusion_figure(
                     matrix, "Random forest — mekânsal 1 km test (satır normalize)"),
                 "model_karsilastirmasi": metric_figure(metrics)},
        notes=[
            "Karışıklık matrisi 00-16'daki aynı GroupShuffleSplit (1 km ızgara, tohum 42) "
            "ile yeniden hesaplandı; kayıtlı modeller değiştirilmedi.",
            "Yüksek doğruluk sınıf dengesizliğinden gelir (%90 görünür hasar yok).",
            *report.get("limitations", []),
            DISCLAIMER,
        ],
    )


def data_quality_report(root: Path) -> Report:
    """Rows, completeness, geometry validity, duplicates and checksum for each dataset."""
    import geopandas as gpd

    from earthquake_damage.ui.overview import DATA_SOURCES

    root = Path(root)
    rows = []
    for key, entry in DATA_SOURCES.items():
        path = root / entry["path"]
        record = {"Veri seti": entry["name"], "Sprint": entry["sprint"], "Dosya": entry["path"]}
        if not path.exists():
            rows.append({**record, "Durum": "eksik"})
            continue
        if path.suffix in {".geojson", ".parquet"}:
            frame = gpd.read_parquet(path) if path.suffix == ".parquet" else gpd.read_file(path)
            geometry = frame.geometry
            record.update({
                "Geçersiz geometri": int((~geometry.is_valid).sum()),
                "Boş geometri": int((geometry.is_empty | geometry.isna()).sum()),
                "Yinelenen geometri": int(geometry.to_wkb().duplicated().sum()),
            })
            table = pd.DataFrame(frame.drop(columns="geometry"))
        else:
            table = pd.read_csv(path)
        cells = table.size or 1
        record.update({
            "Durum": "yerel (Git dışı)" if entry["path"].startswith("data/external/") else "depoda",
            "Satır": len(table),
            "Sütun": table.shape[1],
            "Doluluk": round(1 - table.isna().sum().sum() / cells, 4),
            "Yinelenen satır": int(table.astype(str).duplicated().sum()),
            "SHA-256": _sha256(path)[:16] + "…",
        })
        rows.append(record)
    quality = pd.DataFrame(rows)
    validation = []
    for label, path in (
        ("00-19 yeniden yapılanma", "reports/sprint_00-19/reconstruction_validation.json"),
        ("00-20 mekânsal analiz", "reports/sprint_00-20/spatial_analysis_validation.json"),
        ("00-18 uydu taraması", "reports/sprint_00-18/satellite_change_validation.json"),
    ):
        document = root / path
        if document.exists():
            content = json.loads(document.read_text(encoding="utf-8"))
            validation.append({"Rapor": label, "Durum": content.get("status"),
                               "Tekrar okuma": content.get("roundtrip_valid"),
                               "Üretim": str(content.get("generated_at_utc", ""))[:19]})
    official = pd.read_csv(root / DATA_SOURCES["official"]["path"])
    summary = [
        ("Kapsam", "Veri seti", _fmt(len(quality))),
        ("Kapsam", "Eksik veri seti", _fmt(int((quality["Durum"] == "eksik").sum()))),
        ("Kapsam", "Yalnız yerel veri seti",
         _fmt(int(quality["Durum"].eq("yerel (Git dışı)").sum()))),
        ("Geometri", "Toplam geçersiz geometri",
         _fmt(int(quality.get("Geçersiz geometri", pd.Series(dtype=float)).fillna(0).sum()))),
        ("Resmî kayıtlar", "Toplam kayıt", _fmt(int(official["official_total"].sum()))),
        ("Resmî kayıtlar", "Mahalle", _fmt(len(official))),
    ]
    figure, axis = _figure(7, 3.6)
    present = quality.dropna(subset=["Doluluk"]) if "Doluluk" in quality else quality.iloc[:0]
    axis.barh(present["Veri seti"], present["Doluluk"], color="#2F6FDE")
    axis.set_xlim(0, 1)
    axis.set_xlabel("Doluluk (boş olmayan hücre payı)")
    axis.set_title("Veri setlerinin doluluğu", fontsize=10)
    axis.tick_params(axis="y", labelsize=7)
    figure.tight_layout()
    return Report(
        kind="veri_kalitesi", title="Veri kalitesi raporu", subtitle="Tüm veri setleri",
        summary=summary,
        tables={"Veri setleri": quality, "Doğrulama raporları": pd.DataFrame(validation)},
        figures={"doluluk": figure},
        notes=[
            "Yerel (Git dışı) veri setleri lisans veya boyut nedeniyle depoda değildir; "
            "karma değerleri kendi yan dosyalarında ve envanterdedir.",
            "Boş hücreler her zaman hata değildir: ör. EMSR648 kapsamı dışındaki mahallelerde "
            "EMSR payı bilinçli olarak boş bırakılır.",
            "Yeniden yapılanma haritasındaki yinelenen geometriler tasarım gereğidir: kabul "
            "edilmeyen (belirsiz) eşleşmelerde 2023 ve 2026 tarafları ayrı birimlerdir ve "
            "aynı ayak izini paylaşabilir. 2023 OSM kesitindeki 16 yinelenen ayak izi OSM'nin "
            "kendisindendir.",
            DISCLAIMER,
        ],
    )


# ---------------------------------------------------------------------------
# Exporters
# ---------------------------------------------------------------------------


def summary_frame(report: Report) -> pd.DataFrame:
    return pd.DataFrame(report.summary, columns=["Bölüm", "Alan", "Değer"])


def to_csv(report: Report) -> bytes:
    """UTF-8 (with BOM, for Excel) long table: summary rows, then every table row."""
    parts = [summary_frame(report).assign(Tablo="Özet")]
    for name, table in report.tables.items():
        long = table.map(_cell).reset_index(drop=True)
        long = long.melt(ignore_index=False, var_name="Alan", value_name="Değer")
        long["Bölüm"] = long.index.map(lambda i: f"satır {i + 1}")
        parts.append(long.assign(Tablo=name).reset_index(drop=True))
    combined = pd.concat(parts, ignore_index=True)[["Tablo", "Bölüm", "Alan", "Değer"]]
    return combined.to_csv(index=False).encode("utf-8-sig")


def to_excel(report: Report) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        header = pd.DataFrame({"": [report.title, report.subtitle,
                                    f"Üretim: {report.generated_at}"]})
        header.to_excel(writer, sheet_name="Özet", index=False, header=False)
        summary_frame(report).to_excel(writer, sheet_name="Özet", index=False, startrow=4)
        used = {"Özet"}
        for name, table in report.tables.items():
            sheet = _sheet_name(name, used)
            table.to_excel(writer, sheet_name=sheet, index=False)
        pd.DataFrame({"Not": report.notes}).to_excel(writer, sheet_name="Notlar", index=False)
        for sheet in writer.sheets.values():
            for column in sheet.columns:
                width = max(len(str(cell.value or "")) for cell in column)
                sheet.column_dimensions[column[0].column_letter].width = min(60, max(10, width + 2))
    return buffer.getvalue()


def _sheet_name(name: str, used: set[str]) -> str:
    base = "".join(c for c in name if c not in r"[]:*?/\\")[:28] or "Tablo"
    candidate, counter = base, 2
    while candidate in used:
        candidate, counter = f"{base[:25]}_{counter}", counter + 1
    used.add(candidate)
    return candidate


def to_png(figure) -> bytes:
    buffer = io.BytesIO()
    figure.savefig(buffer, format="png", dpi=150, bbox_inches="tight", facecolor="white")
    return buffer.getvalue()


def to_pdf(report: Report) -> bytes:
    """Multi-page A4 PDF: cover with summary, one page per table (paginated), figures, notes."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    a4 = (8.27, 11.69)
    buffer = io.BytesIO()
    with PdfPages(buffer, metadata={"Title": f"{report.title} — {report.subtitle}",
                                    "Creator": "earthquake-building-damage-analysis"}) as pdf:
        lines = [(report.title, 18, "bold"), (report.subtitle, 13, "normal"),
                 (f"Üretim: {report.generated_at}", 9, "normal"), ("", 8, "normal")]
        section = None
        for name, key, value in report.summary:
            if name != section:
                lines.append((name, 11, "bold"))
                section = name
            for k, wrapped in enumerate(textwrap.wrap(f"{key}: {value}", 95) or [""]):
                lines.append(("    " + wrapped if k else wrapped, 9, "normal"))
        _text_pages(pdf, lines, a4)
        for name, table in report.tables.items():
            _table_pages(pdf, name, table, a4)
        for figure in report.figures.values():
            pdf.savefig(figure, bbox_inches="tight")
        notes = [("Notlar ve sınırlılıklar", 13, "bold")]
        for note in report.notes:
            for k, wrapped in enumerate(textwrap.wrap(note, 95)):
                notes.append(("• " + wrapped if k == 0 else "  " + wrapped, 9, "normal"))
        _text_pages(pdf, notes, a4)
    plt.close("all")
    return buffer.getvalue()


def _text_pages(pdf, lines, size, per_page: int = 52) -> None:
    import matplotlib.pyplot as plt

    for start in range(0, len(lines), per_page):
        figure = plt.figure(figsize=size)
        y = 0.95
        for text, fontsize, weight in lines[start:start + per_page]:
            figure.text(0.08, y, text, fontsize=fontsize, fontweight=weight, va="top")
            y -= 0.017 * max(fontsize, 9) / 9
        pdf.savefig(figure)
        plt.close(figure)


def _table_pages(pdf, name: str, table: pd.DataFrame, size, rows_per_page: int = 32) -> None:
    import matplotlib.pyplot as plt

    shown = table.copy()
    for column in shown.columns:
        if pd.api.types.is_float_dtype(shown[column]):
            shown[column] = shown[column].map(lambda v: _fmt(v, 3))
    shown = shown.map(_cell).map(lambda v: v if len(v) <= 28 else v[:27] + "…")
    pages = max(1, int(np.ceil(len(shown) / rows_per_page)))
    for page in range(pages):
        chunk = shown.iloc[page * rows_per_page:(page + 1) * rows_per_page]
        figure, axis = plt.subplots(figsize=size)
        axis.set_axis_off()
        title = name if pages == 1 else f"{name} ({page + 1}/{pages})"
        axis.set_title(title, fontsize=12, fontweight="bold", loc="left")
        if chunk.empty:
            axis.text(0, 0.9, "Kayıt yok.", fontsize=9)
        else:
            grid = axis.table(cellText=chunk.to_numpy(), colLabels=list(chunk.columns),
                              loc="upper left", cellLoc="left")
            grid.auto_set_font_size(False)
            grid.set_fontsize(6.5 if chunk.shape[1] > 6 else 7.5)
            grid.scale(1, 1.25)
        pdf.savefig(figure, bbox_inches="tight")
        plt.close(figure)


EXPORTERS = {"csv": to_csv, "xlsx": to_excel, "pdf": to_pdf}
MIME_TYPES = {
    "csv": "text/csv",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pdf": "application/pdf",
    "png": "image/png",
}
