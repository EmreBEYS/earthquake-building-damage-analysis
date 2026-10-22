
from pathlib import Path
import hashlib
import json
import re
import unicodedata

import pymupdf
import pandas as pd


# ============================================================
# 1. KLASOR YOLLARI
# ============================================================

BASE = Path(__file__).resolve().parent.parent

PDF_DIR = BASE / "data" / "raw" / "official_damage"

OUTPUT_DIR = BASE / "data" / "interim" / "official_damage"

CACHE_DIR = OUTPUT_DIR / "cache"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. VERI SETI SUTUNLARI
# ============================================================

COLUMNS = [
    "person",
    "mahalle",
    "aski_kodu",
    "sokak",
    "bina_numarasi",
    "hasar_durumu",
    "itiraz_sonucu",
    "afet_adi",
    "afet_siddeti",
    "afet_tarihi",
    "mahkeme_sonucu",
    "source_pdf",
    "source_page",
]



DAMAGE_CLASSES = {
    "HASARSIZ": "Hasarsiz",
    "AZHASARLI": "Az hasarli",
    "ORTAHASARLI": "Orta hasarli",
    "AGIRHASARLI": "Agir hasarli",
    "ACILYIKTIRILACAK": "Acil yiktirilacak",
    "ACILYIKILACAK": "Acil yiktirilacak",
    "YIKIK": "Yikik",
}

ASSESSMENT_STATUSES = {
    "DEGERLENDIRMEDISI": "DEGERLENDIRMEDISI",
    "TESPITYAPILAMADI": "TESPITYAPILAMADI",
    "GIRILEMEYENBINA": "GIRILEMEYENBINA",
}



# ============================================================
# 3. METIN TEMIZLEME
# ============================================================

def clean_text(value):
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value)
    ).strip()


def normalize_key(value):
    text = clean_text(value).upper()

    text = text.replace("İ", "I")
    text = text.replace("ı", "I")

    text = unicodedata.normalize("NFKD", text)

    text = "".join(
        char
        for char in text
        if not unicodedata.combining(char)
    )

    return re.sub(
        r"[^A-Z0-9]",
        "",
        text
    )


def normalize_damage(value):
    key = normalize_key(value)

    return DAMAGE_CLASSES.get(
        key,
        "Bilinmeyen"
    )


# ============================================================
# 4. CACHE DOSYA YOLLARI
# ============================================================

def cache_paths(pdf_file):
    relative = pdf_file.relative_to(PDF_DIR)

    key = hashlib.sha256(
        str(relative).encode("utf-8")
    ).hexdigest()[:16]

    cache_csv = CACHE_DIR / f"{key}.csv"
    cache_json = CACHE_DIR / f"{key}.json"

    return cache_csv, cache_json


# ============================================================
# 5. PDF VERI CIKARMA
# ============================================================

def process_pdf(pdf_file):
    person = pdf_file.parent.name
    mahalle = pdf_file.stem

    records = []

    rejected = 0
    raw_rows = 0

    unknown_classes = {}
    missing_pages = []
    page_errors = []

    with pymupdf.open(pdf_file) as doc:
        page_count = len(doc)

        for page_no, page in enumerate(doc, start=1):

            if page_no == 1 or page_no % 10 == 0:
                print(
                    f"  Sayfa {page_no}/{page_count}",
                    flush=True
                )

            try:
                tables = page.find_tables(
                    strategy="lines"
                )
            except Exception as error:
                page_errors.append({
                    "page": page_no,
                    "error": str(error)
                })
                print(
                    f"  Sayfa {page_no} okunamadi:",
                    type(error).__name__
                )
                continue

            if not tables.tables:
                missing_pages.append(page_no)

            for table in tables.tables:
                for row in table.extract():

                    raw_rows += 1

                    if len(row) != 10:
                        rejected += 1
                        continue

                    values = [
                        clean_text(value)
                        for value in row
                    ]

                    code = normalize_key(values[0])

                    # Ornek raporlarda aski kodu 5 karakter.
                    # Farkli bicimler kalite kontrol icin reddedilir.
                    if not re.fullmatch(
                        r"[A-Z0-9]{5}",
                        code
                    ):
                        rejected += 1
                        continue

                    damage = normalize_damage(
                        values[3]
                    )

                    if damage == "Bilinmeyen":
                        rejected += 1

                        key = normalize_key(values[3])

                        unknown_classes[key] = (
                            unknown_classes.get(key, 0) + 1
                        )
                        continue

                    records.append({
                        "person": person,
                        "mahalle": mahalle,
                        "aski_kodu": code,
                        "sokak": values[1],
                        "bina_numarasi": values[2],
                        "hasar_durumu": damage,
                        "itiraz_sonucu": values[4],
                        "afet_adi": values[5],
                        "afet_siddeti": values[6],
                        "afet_tarihi": values[7],
                        "mahkeme_sonucu": values[8],
                        "source_pdf": pdf_file.name,
                        "source_page": page_no,
                    })

    quality = {
        "person": person,
        "pdf": pdf_file.name,
        "pages": page_count,
        "raw_rows": raw_rows,
        "accepted_rows": len(records),
        "rejected_rows": rejected,
        "pages_without_tables": missing_pages,
        "unknown_classes": unknown_classes,
        "page_errors": page_errors,
    }

    data = pd.DataFrame(
        records,
        columns=COLUMNS
    )

    return data, quality


# ============================================================
# 6. CACHE KAYDETME
# ============================================================

def save_cache(data, quality, cache_csv, cache_json):

    # ONEMLI: CSV ve JSON gecici dosyalari farkli!
    temp_csv = cache_csv.with_suffix(".csv.tmp")
    temp_json = cache_json.with_suffix(".json.tmp")

    data.to_csv(
        temp_csv,
        index=False,
        encoding="utf-8-sig"
    )

    temp_json.write_text(
        json.dumps(
            quality,
            ensure_ascii=False,
            indent=2
        ),
        encoding="utf-8"
    )

    temp_csv.replace(cache_csv)
    temp_json.replace(cache_json)


# ============================================================
# 7. CACHE YUKLEME
# ============================================================

def load_or_process(pdf_file):

    cache_csv, cache_json = cache_paths(pdf_file)

    use_cache = (
        cache_csv.exists()
        and cache_json.exists()
        and cache_csv.stat().st_mtime >= pdf_file.stat().st_mtime
        and cache_json.stat().st_mtime >= pdf_file.stat().st_mtime
    )

    if use_cache:
        try:
            print("  Onbellekten yukleniyor.")

            data = pd.read_csv(
                cache_csv,
                dtype=str,
                keep_default_na=False
            )

            quality = json.loads(
                cache_json.read_text(
                    encoding="utf-8"
                )
            )

            return data, quality

        except Exception as error:
            print(
                "  Cache okunamadi, PDF yeniden islenecek:",
                type(error).__name__
            )

    data, quality = process_pdf(pdf_file)

    save_cache(
        data,
        quality,
        cache_csv,
        cache_json
    )

    return data, quality


# ============================================================
# 8. ANA ISLEM
# ============================================================

def main():

    pdf_files = sorted(
        PDF_DIR.rglob("*.pdf")
    )

    print("\nTOPLU RESMI HASAR VERISI")
    print("=" * 50)

    print("Bulunan PDF:", len(pdf_files))

    if not pdf_files:
        print("PDF dosyasi bulunamadi.")
        return

    all_data = []
    quality_reports = []
    failed_files = []

    for index, pdf_file in enumerate(
        pdf_files,
        start=1
    ):

        print(
            f"\n[{index}/{len(pdf_files)}] "
            f"{pdf_file.name}",
            flush=True
        )

        try:
            data, quality = load_or_process(
                pdf_file
            )

            all_data.append(data)
            quality_reports.append(quality)

            print(
                "  Kabul edilen:",
                quality["accepted_rows"]
            )

            print(
                "  Reddedilen:",
                quality["rejected_rows"]
            )

        except Exception as error:

            print(
                "  PDF ISLEME HATASI:",
                type(error).__name__
            )

            print("  Ayrinti:", error)

            failed_files.append(
                str(pdf_file)
            )

            continue

    if not all_data:
        print("\nHicbir PDF islenemedi.")
        return

    # ========================================================
    # 9. VERILERI BIRLESTIR
    # ========================================================

    df = pd.concat(
        all_data,
        ignore_index=True
    )

    qa = pd.DataFrame(
        quality_reports
    )

    # Ayni mahalle + aski kodu birden fazla gorunebilir.
    # Kayitlari silmiyoruz; inceleme icin isaretliyoruz.
    df["possible_duplicate"] = df.duplicated(
        subset=[
            "person",
            "mahalle",
            "aski_kodu"
        ],
        keep=False
    )

    duplicates = df[
        df["possible_duplicate"]
    ].copy()

    # ========================================================
    # 10. CIKTI DOSYALARI
    # ========================================================

    df.to_csv(
        OUTPUT_DIR / "official_damage_records.csv",
        index=False,
        encoding="utf-8-sig"
    )

    duplicates.to_csv(
        OUTPUT_DIR / "duplicate_candidates.csv",
        index=False,
        encoding="utf-8-sig"
    )

    qa_export = qa.copy()

    for column in [
        "pages_without_tables",
        "unknown_classes",
        "page_errors"
    ]:
        qa_export[column] = qa_export[column].apply(
            lambda value: json.dumps(
                value,
                ensure_ascii=False
            )
        )

    qa_export.to_csv(
        OUTPUT_DIR / "extraction_quality_report.csv",
        index=False,
        encoding="utf-8-sig"
    )

    # ========================================================
    # 11. SONUC RAPORU
    # ========================================================

    print("\n" + "=" * 50)
    print("VERI SETI SONUCLARI")
    print("=" * 50)

    print("Bulunan PDF:", len(pdf_files))
    print("Islenen PDF:", len(quality_reports))
    print("Basarisiz PDF:", len(failed_files))

    print(
        "Toplam ham satir:",
        qa["raw_rows"].sum()
    )

    print(
        "Kabul edilen kayit:",
        len(df)
    )

    print(
        "Tekrar adayi kayit:",
        len(duplicates)
    )

    print("\nHASAR SINIFI DAGILIMI")

    print(
        df["hasar_durumu"].value_counts(
            dropna=False
        ).to_string()
    )

    print("\nKALITE KONTROL")

    print(
        qa[
            [
                "pdf",
                "accepted_rows",
                "rejected_rows"
            ]
        ].to_string(index=False)
    )

    print("\nTABLO BULUNAMAYAN SAYFALAR")

    for report in quality_reports:
        if report["pages_without_tables"]:
            print(
                report["pdf"],
                report["pages_without_tables"]
            )

    print("\nBILINMEYEN HASAR SINIFLARI")

    for report in quality_reports:
        if report["unknown_classes"]:
            print(
                report["pdf"],
                report["unknown_classes"]
            )

    print("\nSAYFA HATALARI")

    for report in quality_reports:
        if report["page_errors"]:
            print(
                report["pdf"],
                report["page_errors"]
            )

    if failed_files:
        print("\nBASARISIZ PDF DOSYALARI")

        for file in failed_files:
            print(file)

    print("\nCIKTI KLASORU:")
    print(OUTPUT_DIR)

    print("\nToplu islem tamamlandi.")
    print(
        "Not: Kalite kontrol yapilmadan "
        "egitim verisi olarak kullanmayin."
    )


if __name__ == "__main__":
    main()
