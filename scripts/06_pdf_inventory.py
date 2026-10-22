
from pathlib import Path
import fitz
import pandas as pd


BASE = Path(__file__).resolve().parent.parent

PDF_DIR = BASE / "data/raw/official_damage"
OUTPUT = BASE / "data/interim/official_damage"

OUTPUT.mkdir(parents=True, exist_ok=True)

records = []

for pdf_file in sorted(PDF_DIR.rglob("*.pdf")):
    with fitz.open(pdf_file) as doc:
        page_count = len(doc)

        text_pages = 0

        for page in doc:
            text = page.get_text("text")

            if len(text.strip()) > 50:
                text_pages += 1

        records.append({
            "person": pdf_file.parent.name,
            "filename": pdf_file.name,
            "page_count": page_count,
            "text_pages": text_pages,
            "scanned_pages": page_count - text_pages
        })

df = pd.DataFrame(records)

print("\nPDF ENVANTER OZETI")
print(df.to_string(index=False))

if not df.empty:
    print("\nToplam PDF:", len(df))
    print("Toplam sayfa:", df["page_count"].sum())

df.to_csv(
    OUTPUT / "pdf_inventory.csv",
    index=False,
    encoding="utf-8-sig"
)
