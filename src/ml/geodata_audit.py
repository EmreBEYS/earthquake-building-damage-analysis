from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]

EXTENSIONS = {
    ".shp", ".gpkg", ".geojson",
    ".gjson", ".parquet", ".tif",
    ".tiff", ".fgb", ".csv"
}

EXCLUDE_DIRS = {
    ".git", ".venv", "node_modules",
    "__pycache__", "cache"
}


def main():
    print("=== COGRAFI VERI ENVANTERI ===")

    files = []

    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue

        if any(
            part in EXCLUDE_DIRS
            for part in path.parts
        ):
            continue

        if path.suffix.lower() not in EXTENSIONS:
            continue

        files.append(path)

    files.sort()

    for path in files:
        relative = path.relative_to(ROOT)
        size_mb = path.stat().st_size / (1024 ** 2)

        print(
            f"{relative} | {size_mb:.2f} MB"
        )

    print(f"\nToplam dosya: {len(files)}")


if __name__ == "__main__":
    main()
