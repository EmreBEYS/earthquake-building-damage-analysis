
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

INPUT = (
    ROOT / "reports" / "sprint_00-10"
    / "v3_name_review.csv"
)

OUTPUT = (
    ROOT / "reports" / "sprint_00-10"
    / "v3_name_mapping.csv"
)

# Sadece belirgin yazim / bosluk farklari.
# Bu liste bina veya adres eslesmesi yapmaz.
APPROVED = {
    "sehit feyzi": "SEHITFEVZI",
    "iskender": "ISKERDER",
    "merkez beydagi": "MERKEZ BEYDAĞ",
    "basharik": "BASHANK",
    "ferhadiye": "FARHADIYE",
    "kavaklibag": "KAVLIKBAG",
    "haci abdi": "HACIABDI",
    "hoca ahmet yesevi": "HOCAAHMETYESEVI",
    "cemal gursel": "CEMALGURSEL",
    "yavuz selim": "YAVUZSELIM",
}

REVIEW = {
    "b.mustafa pasa",
    "k.huseyinbey",
    "izzetiye",
    "hamidiye",
    "gunduzbey",
}


def main():
    df = pd.read_csv(INPUT)

    rows = []

    for _, row in df.iterrows():
        key = row["normalized"]

        if key in APPROVED:
            status = "candidate"
            target = APPROVED[key]
        elif key in REVIEW:
            status = "manual_review"
            target = ""
        else:
            status = "unresolved"
            target = ""

        rows.append({
            "osm_mahalle": row["osm_mahalle"],
            "normalized": key,
            "official_candidate": target,
            "status": status
        })

    result = pd.DataFrame(rows)

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    result.to_csv(
        OUTPUT,
        index=False,
        encoding="utf-8-sig"
    )

    print("=== V3 ISIM ESLESTIRME ===")
    print(result.to_string(index=False))

    print("\nDURUM DAGILIMI:")
    print(result["status"].value_counts())

    print(f"\nRapor: {OUTPUT}")


if __name__ == "__main__":
    main()
