import json
import tempfile
import unittest
from pathlib import Path

from scripts.acquire_data import install_immutable, sha256
from scripts.validate_data import geojson_summary


class DataWorkflowTests(unittest.TestCase):
    def test_install_immutable_preserves_existing_bytes(self) -> None:
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            root = Path(directory)
            source = root / "source.bin"
            destination = root / "raw" / "source.bin"
            source.write_bytes(b"original")
            installed = install_immutable(source, destination, sha256(source))
            self.assertEqual(installed.read_bytes(), b"original")

            source.write_bytes(b"changed")
            with self.assertRaises(FileExistsError):
                install_immutable(source, destination, None)
            self.assertEqual(destination.read_bytes(), b"original")

    def test_geojson_summary_counts_and_bounds(self) -> None:
        data = {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {"type": "Point", "coordinates": [38.2, 38.3]},
                },
                {
                    "type": "Feature",
                    "properties": {},
                    "geometry": {
                        "type": "LineString",
                        "coordinates": [[38.1, 38.4], [38.5, 38.2]],
                    },
                },
            ],
        }
        summary = geojson_summary(json.loads(json.dumps(data)))
        self.assertEqual(summary["feature_count"], 2)
        self.assertEqual(summary["geometry_types"], {"LineString": 1, "Point": 1})
        self.assertEqual(summary["bbox"], [38.1, 38.2, 38.5, 38.4])


if __name__ == "__main__":
    unittest.main()
