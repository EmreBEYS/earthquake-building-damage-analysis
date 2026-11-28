"""Generate Sprint 00-23 reports: model performance and data quality (PDF, Excel, PNG).

Neighbourhood and building reports are produced on demand in the dashboard
(Rapor & İndirme) or with ``--neighborhood`` / ``--building``.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from earthquake_damage import reporting  # noqa: E402

OUTPUT = ROOT / "reports/sprint_00-23"


def write(report: reporting.Report, stem: str) -> list[str]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    written = []
    for extension, exporter in reporting.EXPORTERS.items():
        path = OUTPUT / f"{stem}.{extension}"
        path.write_bytes(exporter(report))
        written.append(path.relative_to(ROOT).as_posix())
    for name, figure in report.figures.items():
        path = OUTPUT / f"{stem}_{name}.png"
        path.write_bytes(reporting.to_png(figure))
        written.append(path.relative_to(ROOT).as_posix())
    return written


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--neighborhood", help="Also write a report for this neighbourhood")
    parser.add_argument("--building", help="Also write a report for this EMSR648 feature_id")
    args = parser.parse_args()
    written = {"confusion_cache": reporting.write_confusion_cache(ROOT)["evidence"]}
    context = reporting.load_context(ROOT)
    written["model"] = write(reporting.model_performance_report(context),
                             "model_performance_report")
    written["data_quality"] = write(reporting.data_quality_report(ROOT), "data_quality_report")
    if args.neighborhood:
        report = reporting.neighborhood_report(context, args.neighborhood)
        written["neighborhood"] = write(report, report.slug())
    if args.building:
        report = reporting.building_report(context, args.building)
        written["building"] = write(report, report.slug())
    print(json.dumps(written, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
