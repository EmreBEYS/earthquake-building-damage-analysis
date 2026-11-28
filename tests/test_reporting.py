import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from earthquake_damage import reporting
from earthquake_damage.reporting import (
    CONFUSION_CACHE,
    Report,
    _cell,
    _fmt,
    _sheet_name,
    to_csv,
    to_excel,
    to_pdf,
    to_png,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def context():
    return reporting.load_context(ROOT)


def _small_report() -> Report:
    figure, axis = reporting._figure(3, 2)
    axis.plot([0, 1], [0, 1])
    return Report(
        kind="test", title="Başlık", subtitle="Şehir/İlçe: ö",
        summary=[("Bölüm", "Alan", "değer"), ("Bölüm", "Boş", "—")],
        tables={"Tablo [1]": pd.DataFrame({"a": [1.5, np.nan], "b": ["x", None]}),
                "Tablo [1]?": pd.DataFrame({"c": [1]})},
        figures={"çizgi": figure}, notes=["Not"],
    )


def test_formatting_helpers():
    assert _fmt(46563) == "46.563"
    assert _fmt(1364.04, 1) == "1.364,0"
    assert _fmt(float("nan")) == "—" and _fmt(True) == "evet"
    assert _cell(np.nan) == "—" and _cell(pd.NA) == "—" and _cell(None) == "—"
    assert _cell(3) == "3"
    used: set[str] = set()
    assert _sheet_name("Tablo [1]", used) == "Tablo 1"
    assert _sheet_name("Tablo [1]?", used) == "Tablo 1_2"


def test_exporters_write_valid_files():
    report = _small_report()
    csv = to_csv(report)
    assert csv.startswith(b"\xef\xbb\xbf")
    frame = pd.read_csv(io.BytesIO(csv), encoding="utf-8-sig")
    assert set(frame["Tablo"]) == {"Özet", "Tablo [1]", "Tablo [1]?"}
    assert "—" in set(frame["Değer"])
    sheets = pd.read_excel(io.BytesIO(to_excel(report)), sheet_name=None)
    assert {"Özet", "Tablo 1", "Tablo 1_2", "Notlar"} <= set(sheets)
    pdf = to_pdf(report)
    assert pdf.startswith(b"%PDF")
    import pymupdf

    document = pymupdf.open(stream=pdf, filetype="pdf")
    text = "".join(page.get_text() for page in document)
    assert "Başlık" in text and "Notlar ve sınırlılıklar" in text
    assert to_png(report.figures["çizgi"]).startswith(b"\x89PNG")


def test_neighborhood_report_matches_comparison_table(context):
    report = reporting.neighborhood_report(context, "Dabakhane Mahallesi")
    values = {key: value for _, key, value in report.summary}
    assert values["İlçe"] == "Battalgazi"
    assert values["Kayıt"] == "142"
    assert values["Ağır hasar oranı"] == "%89,4"
    assert values["Net OSM bina kaybı 2023→2026"] == "%79,5"
    classes = report.tables["Resmî hasar sınıfları"]
    assert classes["Kayıt"].sum() == 142
    assert set(report.figures) == {"resmi_hasar_siniflari", "konum"}
    with pytest.raises(KeyError):
        reporting.neighborhood_report(context, "Yok Mahallesi")


def test_building_report_uses_building_details(context):
    feature = context["details"]["feature_id"].iloc[0]
    report = reporting.building_report(context, feature)
    values = {key: value for _, key, value in report.summary}
    assert values["Poligon ID"] == feature
    assert report.tables["Model olasılıkları"]["Olasılık"].sum() == pytest.approx(1, abs=1e-3)
    with pytest.raises(KeyError):
        reporting.building_report(context, "missing")


def test_model_report_reproduces_sprint_00_16_macro_f1(context):
    report = reporting.model_performance_report(context)
    values = {key: value for _, key, value in report.summary}
    assert values["Karışıklık matrisinden macro-F1"].endswith("(00-16 ile aynı)")
    matrix = report.tables["Karışıklık matrisi (mekânsal, random forest)"]
    assert matrix.drop(columns=matrix.columns[0]).to_numpy().sum() == 583


def test_confusion_cache_is_used_without_models(tmp_path, monkeypatch):
    cache = tmp_path / CONFUSION_CACHE
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps({
        "labels": ["a", "b"], "matrix": [[3, 1], [0, 2]],
        "evidence": {"test_rows": 6, "macro_f1": 0.5, "per_class_f1": {"a": 0.8, "b": 0.6}},
    }), encoding="utf-8")

    def missing(_root):
        raise FileNotFoundError("models")

    monkeypatch.setattr(reporting, "spatial_confusion_matrix", missing)
    matrix, evidence = reporting.cached_confusion_matrix(tmp_path)
    assert matrix.loc["a", "b"] == 1 and evidence["macro_f1"] == 0.5
    with pytest.raises(FileNotFoundError):
        reporting.cached_confusion_matrix(tmp_path / "empty")


def test_data_quality_report_covers_every_registered_source():
    from earthquake_damage.ui.overview import DATA_SOURCES

    report = reporting.data_quality_report(ROOT)
    table = report.tables["Veri setleri"]
    assert len(table) == len(DATA_SOURCES)
    official = table[table["Veri seti"] == DATA_SOURCES["official"]["name"]].iloc[0]
    assert official["Satır"] == 87 and official["Durum"] == "depoda"


def test_committed_reports_exist():
    for name in ("model_performance_report.pdf", "model_performance_report.xlsx",
                 "data_quality_report.pdf", "data_quality_report.xlsx",
                 "spatial_confusion_matrix.json"):
        assert (ROOT / "reports/sprint_00-23" / name).stat().st_size > 0
