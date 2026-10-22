
from pathlib import Path
import pymupdf
import pandas as pd

BASE = Path(__file__).resolve().parent.parent

PDF_FILE = (
    BASE / "data" / "raw"
    / "official_damage" / "person_01" / "yakinca.pdf"
)

OUTPUT_DIR = (
    BASE / "data" / "interim" / "official_damage"
)

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def main():
    if not PDF_FILE.exists():
        raise FileNotFoundError(PDF_FILE)

    records = []
    missing_pages = []
    table_count = 0

    with pymupdf.open(PDF_FILE) as doc:
        print("PDF:", PDF_FILE.name)
        print("PDF sayfa sayisi:", len(doc))

        for page_no, page in enumerate(doc, start=1):
            tables = page.find_tables(strategy="lines")

            if not tables.tables:
                missing_pages.append(page_no)

            for table in tables.tables:
                table_count += 1

                for row in table.extract():
                    records.append({
                        "page": page_no,
                        "table_id": table_count,
                        "columns_found": len(row),
                        "values": row
                    })

    df = pd.DataFrame(records)

    print("\nBulunan tablo:", table_count)
    print("Cikarilan ham satir:", len(df))

    if not df.empty:
        print("\nSutun sayisi dagilimi:")
        print(df["columns_found"].value_counts())

        print("\nILK 10 SATIR")
        print("-" * 50)

        for index, record in enumerate(
            records[:10], start=1
        ):
            print(f"\nSatir {index}")
            print("Sayfa:", record["page"])

            for col, value in enumerate(record["values"]):
                # Hassas bilgileri terminale yazma
                if col in (0, 1, 2):
                    value = "[GIZLI]"

                print(f"Sutun {col}: {value}")

        df.to_json(
            OUTPUT_DIR / "yakinca_raw_tables.json",
            orient="records",
            force_ascii=False,
            indent=2
        )

    print("\nTABLO BULUNAMAYAN SAYFALAR")
    print(missing_pages)

    # Tablo olmayan sayfalarin metin uzunlugu
    with pymupdf.open(PDF_FILE) as doc:
        for page_no in missing_pages:
            page = doc[page_no - 1]
            text = page.get_text("text").strip()

            print(
                f"Sayfa {page_no}: "
                f"{len(text)} karakter"
            )

    print("\nTest tamamlandi.")


if __name__ == "__main__":
    main()
