"""Algorithm checks use committed real Copernicus footprints; no invented result data."""
import json
import tempfile
import unittest
from pathlib import Path

from shapely import STRtree
from shapely.geometry import shape

from earthquake_damage.building_change_analysis import (
    load_snapshot,
    match_buildings,
    repair_polygon,
)

ROOT = Path(__file__).resolve().parents[1]


class BuildingChangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        document = json.loads((ROOT / "data/dashboard/sprint_00-12/"
                               "copernicus_damage_polygons.geojson").read_text())
        cls.geometries = [shape(f["geometry"]) for f in document["features"]]
        cls.geometry = cls.geometries[0]

    def test_identical_real_footprint(self):
        row = match_buildings([self.geometry], [self.geometry])[0]
        self.assertEqual(row["status"], "unchanged")
        self.assertAlmostEqual(row["iou"], 1)

    def test_unmatched_is_never_destroyed(self):
        self.assertEqual(match_buildings([self.geometry], [])[0]["status"], "unmatched")
        self.assertEqual(match_buildings([], [self.geometry])[0]["status"], "newly_mapped")

    def test_duplicate_candidates_are_uncertain(self):
        rows = match_buildings([self.geometry], [self.geometry, self.geometry])
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(r["status"] == "uncertain" for r in rows))
        rows = match_buildings([self.geometry, self.geometry], [self.geometry])
        self.assertTrue(all(r["status"] == "uncertain" for r in rows))

    def test_changed_and_low_overlap_with_real_intersections(self):
        tree = STRtree(self.geometries)
        for i, geometry in enumerate(self.geometries):
            for j in tree.query(geometry, predicate="intersects"):
                if i == j:
                    continue
                other = self.geometries[int(j)]
                area = geometry.intersection(other).area
                iou = area / geometry.union(other).area
                if 0 < iou < 0.99:
                    rows = match_buildings([geometry], [other], iou / 2, (1 + iou) / 2)
                    self.assertEqual(rows[0]["status"], "geometry_changed")
                    rows = match_buildings([geometry], [other], (1 + iou) / 2, 1)
                    self.assertTrue(all(r["status"] == "uncertain" for r in rows))
                    return
        self.fail("No overlapping real footprints found")

    def test_conservation_and_order_invariance(self):
        before = self.geometries[:30]
        after = before[::-1]
        rows = match_buildings(before, after)
        self.assertEqual(sum(r["before_index"] is not None for r in rows), len(before))
        self.assertEqual(sum(r["after_index"] is not None for r in rows), len(after))
        for row in rows:
            if row["status"] == "unchanged":
                self.assertTrue(before[row["before_index"]].equals(after[row["after_index"]]))

    def test_repair_and_threshold_guards(self):
        self.assertIsNone(repair_polygon(None))
        self.assertTrue(repair_polygon(self.geometry).is_valid)
        with self.assertRaises(ValueError):
            match_buildings([], [], 0.9, 0.5)

    def test_wrong_date_and_duplicate_source_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.geojson"
            feature = {"type": "Feature", "geometry": self.geometry.__geo_interface__,
                       "properties": {"@osmId": "way/1",
                                      "@snapshotTimestamp": "2023-02-05T00:00:00Z"}}
            path.write_text(json.dumps({"type": "FeatureCollection", "features": [feature]}))
            with self.assertRaises(ValueError):
                load_snapshot(path, "2022-12-31T00:00:00Z")
            path.write_text(json.dumps({"type": "FeatureCollection",
                                        "features": [feature, feature]}))
            with self.assertRaises(ValueError):
                load_snapshot(path, "2023-02-05T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
